# Codex review: Science Bank backup job (`ops/backup/`)

Branch: `feat/backup-ops` (from `main` at `6b1023f`). Author: Claude. Reviewer: Codex. Status: round 1 review
received and addressed (see "Review round 1" below); ready for a second look. Nothing is deployed,
scheduled, or uploaded. This is a code review of scripts that will later guard the only copy of teachers' work.

## What was asked

Brandon wants the Science Bank database (and `.env`) backed up to an encrypted offsite copy, reusing the pattern
of the existing Life backup pipeline (`/srv/pool/config/dashboard-backups`: age + rclone to Google Drive + ntfy +
a stale-backup watchdog). His instruction: build it, test it, leave it ready, and do not schedule or upload until
he has a real key.

## What was built

All under `ops/backup/` (read `README.md` there first; it is also the operator runbook):

| File | Role |
|---|---|
| `lib.sh` | Config defaults and helpers (logging, notify, markers, artifact-name parsing, recipient validation). |
| `backup-science-bank.sh` | dump, manifest, tar, age, local copy, rclone upload with size check, retention. |
| `check-backup-health.sh` | Watchdog: stale or missing success markers; optional remote listing check. |
| `restore-drill.sh` | Verify signature, decrypt, strict unpack, verify checksums, restore into a throwaway Postgres (no network), compare to manifest; `--extract-to` for real restores. |
| `bundle.py` | Strict extractor and manifest validator used by the drill. |
| `tests/run-tests.sh`, `tests/fixture.sql` | 150 end-to-end checks against scratch resources. |

Design decisions worth challenging:

1. **Separate job from Life's.** Only the age public key, the rclone remote name, and `notify.sh`'s `ntfy_alert`
   function are shared. The Life scripts are not modified.
2. **`pg_dump -Fc`** (custom format) plus a `manifest.json` carrying row counts, schema version, and sha256 of each
   file. The drill checks the dump against the manifest.
3. **`.env` travels inside the encrypted bundle** (it holds `POSTGRES_PASSWORD` and `JWT_SECRET` and exists only
   on the host). `INCLUDE_ENV=0` turns this off.
4. **Recipients file accepts only `age1...` public keys** and refuses any file containing `AGE-SECRET-KEY`, to
   stop a private key being pasted in by mistake.
5. **Retention never prunes below `MIN_KEEP` (3) newest copies**, parsed from the timestamp in the file name, not
   mtime. Only names matching `ARTIFACT_RE` are ever touched.
6. **Upload is verified by size** (`rclone lsjson --include NAME`). Exit code 2 means "local copy kept, upload
   failed", distinct from 1 ("no encrypted copy exists").
7. **Two markers** (`last-local-success`, `last-upload-success`) so the watchdog can tell "backups run but upload
   is broken" from "nothing runs".
8. **Every artifact is signed** (`ssh-keygen -Y sign`, namespace `science-bank-backup`) and the drill verifies the
   signature before decrypting or unpacking anything. See "Review round 1".
9. **The Postgres access is two overridable shell strings** (`DUMP_CMD`, `SQL_CMD`, run via `bash -c`). Defaults
   use `docker compose exec -T postgres sh -c '... $POSTGRES_USER ...'`, so no credentials are parsed. Tests
   replace them with `docker exec` into a scratch container. They are operator config, not user input.

## How to run the tests (safe)

```bash
ops/backup/tests/run-tests.sh          # needs docker, age, age-keygen, rclone, python3, flock
```

Expected: `passed: 150   failed: 0`, about two minutes. It starts one container named `sb-backup-test-<pid>` (no ports
published) and removes it on exit. No real key, no Drive, no ntfy, no production. Two copies can run at the same
time (container and temp names are per-PID); it does need Docker.

## Review round 1: your finding and the fix

**Finding (Medium):** backups were encrypted but not authenticated; `restore-drill.sh` unpacked before validating and
trusted the archive's own manifest, so anyone with the public key who can write to Drive could plant a forged
"latest" that passes the drill.

**Agreed and fixed.** One refinement to the suggested remedy: a signature made at backup time needs the signing
key on the backup host, so "key not on the backup host" cannot hold for signing. What protects you is that
*Drive write access alone* cannot forge a signature and the **verification** key lives off the host. The threat
model table in `ops/backup/README.md` states what this does and does not defend.

What changed:
1. **Signatures.** Each artifact gets an OpenSSH detached signature (`NAME.sig`), self-verified at backup time,
   uploaded (sig first), size-checked, pruned with its artifact, and required by the watchdog's `--check-remote`.
   The backup **refuses to run without a signing key**. The drill verifies against an allowed-signers file (public
   key, kept in the password manager) **before** decrypting; unsigned or wrongly signed files are refused.
2. **Strict unpack** (`bundle.py`): the decrypted tar is opened with Python `tarfile` (tar's own extraction is never
   used); members must be exactly `manifest.json`, `science_bank.dump`, optionally `env`, regular files only, no
   duplicates, no links, devices, directories, absolute or `..` names, and size-capped. Files are written by
   allowlisted name, mode 0600, `O_EXCL`.
3. **Manifest validation before any use:** exact schema, table names `^[a-z_][a-z0-9_]*$` (they go into SQL, now
   also double-quoted), schema version charset, sha256 shape, printable-only strings (no terminal escapes), every
   listed file present and every present file listed.
4. **Replay/rename defence:** the signature covers content, not the file name, so a genuine old backup renamed to
   look new would verify. The drill now requires the signed manifest's `created_at` to match the timestamp in the
   file name (15 minute tolerance).
5. **Defence in depth:** the drill's throwaway Postgres runs with `--network none`.

New tests (73 added): signature present/verifies; unsigned, attacker-signed, altered-after-signing, renamed-old,
and missing-signers all refused; your exact scenario (a newer forged `latest` planted on the remote, unsigned and
attacker-signed) refused while naming the genuine file still works; 13 hostile-but-correctly-signed bundles (path
escape, absolute path, symlink, extra member, missing dump/manifest, directory, duplicate, device, unlisted file,
SQL-injection table name, bad schema version, terminal escape in a string); a missing signing key fails the backup;
signatures follow their artifacts through retention; watchdog flags a remote artifact that lost its signature.
I again broke each new check on purpose and confirmed the tests fail (signature verification skipped, non-regular
members allowed, table-name validation, rename check, unexpected members allowed, backup that never signs).
Two things that exercise taught me: (a) with the member-name allowlist disabled, an absolute-path tar member really
did write outside the work directory, so that test earns its place (it now uses a per-run target path); (b) a
mutant that made every backup fail **hung** the suite, because a test called `age -d` with no file and waited on
stdin. The suite now runs with stdin closed (`exec </dev/null`) and stops with a clear message if the first backup
produces nothing.

## What I already verified, and how

- **The tests pass** (150). I also broke the scripts on purpose and confirmed the tests catch it: private-key guard
  removed (1 check failed), retention ignoring `MIN_KEEP` (3 failed), upload size check removed (**initially NOT
  caught**; I added the truncated-upload test, after which 3 fail), watchdog never alerting (5 fail), drill
  skipping checksums (1 fails). Note the private-key guard is belt and braces: without it the `age1` format check
  still refuses the file, so only the alert wording test fails.
- **Real data, read-only (before the signing change; re-run afterwards, see below).** I ran the default commands (real `docker compose exec` into the live Postgres) with a
  throwaway key, `--no-upload`, `INCLUDE_ENV=0`, and scratch folders, then the drill: 133 KB encrypted, restore
  into a throwaway container passed, all six table counts matched (users 6, questions 33, assessments 6,
  administrations 4, item_results 8, audit_events 69), schema `0005_results_and_variants`. Production row counts
  were unchanged afterwards. The scratch copy and the throwaway key were then deleted.

## What is NOT verified (please look hard here)

1. **Google Drive behaviour.** All upload tests use a local directory as the rclone "remote". I have not run
   `copyto`, `lsjson --files-only --include`, `lsf`, or `deletefile` against `gdrive-backup:`. Check that the
   `lsjson ... --include "$NAME"` size check is valid for Drive (eventual consistency, name quoting in filters),
   and that `rclone lsf | sort -r` ordering assumptions hold.
2. **systemd units.** The unit files are documented in `README.md` only and were never created or validated
   (`systemd-analyze verify` needs files on disk). Please read them for correctness (`OnCalendar` with two lines,
   `Persistent`, `Type=oneshot`).
3. **Linger.** Whether `loginctl` lingering is enabled for the account was not checked (see below).
4. **The Life `notify.sh` interface.** I assumed `ntfy_alert "title" "message" [priority]` with priorities
   `high` and `urgent`, inferred from how the Life scripts call it. I did not read the file.
5. **Shellcheck** is not installed here, so only `bash -n` was run. A shellcheck pass would be welcome.
6. **`ssh-keygen -Y sign/verify` portability.** Tested with the host's OpenSSH (see `ssh-keygen` in the tests).
   Disaster recovery on another OS needs OpenSSH 8.0 or newer; worth confirming the allowed-signers format.
7. **Signing key at rest.** It has no passphrase (unattended runs). Confirm you are comfortable with that trade-off
   and with the README's guidance.

## Things I was not allowed to do, deliberately left alone

The session's permission system blocked these, and I did not work around it:

- Creating a `systemd/` folder with unit files, an installer script, and checking `loginctl` linger ("unauthorized
  persistence"). Consequently there is **no installer**; the README gives the unit text and the commands for
  Brandon to run.
- Reading `notify.sh`, looking for the Life age private key, and listing the Kestrel secrets folder
  ("credential exploration / materialization"). Do not attempt these either.

## Review checklist

Correctness and failure modes
- [ ] Every path that can leave a half-written or plaintext file behind: `mktemp` dir under `$STATE_DIR`, the
  `trap`, `.partial` rename, the plaintext `bundle.tar` (deleted right after encryption), the extracted payload in
  the drill.
- [ ] Exit-code contract (0/1/2/64/75) matches the README and is what the tests assert.
- [ ] `set -uo pipefail` interactions: `dump | ...` pipelines, `$(...)` in `fail` paths, empty arrays (`members`).
- [ ] `name_epoch` / `older_than` parsing, including labelled names (`-pre-deploy`) and the `ARTIFACT_RE` anchors.
- [ ] Retention ordering: `sort -r` on names equals newest-first; `MIN_KEEP` counts only matching names.
- [ ] `flock -n 9` lock scope: held for the whole run, released on exit; the watchdog does not take it.
- [ ] The manifest/dump count race (counts read after the dump) and the drill's tolerance rule (fail only on
  missing table, empty-but-had-rows, schema mismatch).

Security
- [ ] No secret ever reaches the log, stdout, or alert text (`.env` is only copied into the payload, never read
  or printed). The drill prints only `included and checksum-verified`.
- [ ] `umask 077`, `chmod 700` on state and backup dirs, artifact mode 600.
- [ ] Signature flow: sign before copy, self-verify, sig uploaded before the artifact, the drill verifies before
  `age -d`. Anything that could let an unsigned file reach decryption or unpacking.
- [ ] `bundle.py` really cannot write outside `dest` and cannot be made to accept a member it should not.
- [ ] `validate_recipients` cannot be fooled by whitespace, comments, or a key hidden in a comment line.
- [ ] `restore-drill.sh` never copies the identity file and warns on loose permissions.
- [ ] Inputs interpolated into shell: `--label` is regex-restricted; `--from-remote NAME` is matched against
  `ARTIFACT_RE` before use; `TABLES` is config, but check it is not used unquoted in a dangerous place.
- [ ] `rm -rf "${TMP:?}"` and `${WORK:?}` guards (a safety hook flagged unguarded removals once).

Tests
- [ ] Any test that could pass for the wrong reason (I found and fixed one: the truncated-upload gap).
- [ ] The tamper tests really exercise the checksum path (they re-encrypt a modified bundle to the same key).

## Suggested follow-ups (not done)

- A shellcheck pass and fixes.
- If Brandon approves installing systemd units: an `install.sh` with `--dry-run` and validation, and a
  `systemd-analyze verify` step in the tests.
- Optionally a second local copy on another disk, and a monthly scheduled restore drill (needs the private key,
  so it would have to stay manual or use a dedicated drill-only key).

## Report back

Reply with: findings ranked by severity (with file and line), anything you could not verify, and the exact output
of `ops/backup/tests/run-tests.sh` from your run. Do not install timers, upload to Drive, or touch production.
