# Science Bank backups

Encrypted, offsite backups of the Science Bank database (and `.env`), built on the same pieces as the Life app's
backup pipeline in `/srv/pool/config/dashboard-backups` (age encryption, the `gdrive-backup` rclone remote, ntfy
alerts, a dead-man's-switch watchdog), but as a **separate job** so neither can break the other.

**Status: built and tested, not installed.** Nothing here is scheduled, nothing has been uploaded to Google Drive,
and no real key is configured. See "Switching it on".

## What a backup is

```
pg_dump -Fc  +  manifest.json (row counts, schema version, sha256s)  +  .env
        -> tar -> age (public keys only) -> /srv/pool/config/science-bank-backups/science-bank-<UTC timestamp>.tar.age
        -> rclone copyto gdrive-backup:science-bank-backups/   (size verified afterwards)
```

- Only `age` **public** keys are ever on the server. The private key decrypts everything, so it lives in your
  password manager and is brought out only to run a restore drill or a real restore.
- `.env` (database password, `JWT_SECRET`) is inside the encrypted bundle and nowhere else.
- Local copies live under `/srv/pool` (a different disk from the root disk the database volume is on). Retention:
  14 days local, 90 days remote, and **never fewer than the 3 newest copies** whatever their age.
- The whole database is about 10 MB; a backup is about 130 KB encrypted.

## Files

| File | Purpose |
|---|---|
| `lib.sh` | Settings and helpers shared by the scripts. All settings are overridable (env or `~/.config/science-bank-backup/backup.conf`). |
| `backup-science-bank.sh` | The backup. `--label NAME` (e.g. `pre-deploy`), `--no-upload`. Exit 0 ok, 1 failed, 2 kept locally but upload failed, 75 already running. |
| `check-backup-health.sh` | Watchdog. Alerts if the last local or upload success is older than 30 h. `--check-remote` also lists the remote. |
| `restore-drill.sh` | Decrypts with your key, verifies checksums, restores into a throwaway Postgres, compares with the manifest. `--extract-to DIR` only unpacks. |
| `tests/run-tests.sh`, `tests/fixture.sql` | End-to-end tests on scratch resources only (77 checks). |

## Switching it on

Nothing below has been done. Do it in this order.

1. **Make the key, on your own machine** (not this server):
   `age-keygen -o science-bank-backup-key.txt`. Save the **whole file** in your password manager. The line starting
   `# public key: age1...` is the public key.
2. **Install the public key here** (only that one line):
   ```bash
   mkdir -p ~/.config/science-bank-backup
   echo 'age1...your-public-key...' > ~/.config/science-bank-backup/recipients.txt
   ```
   The scripts refuse a recipients file that contains `AGE-SECRET-KEY` or anything that is not an `age1...` key.
3. **Check the remote and alert script exist:** `rclone listremotes` should show `gdrive-backup:`, and
   `/srv/pool/config/dashboard-backups/notify.sh` should exist (alerts go through its `ntfy_alert`). Both are
   reused unchanged; the Life scripts are not modified.
4. **Run it once by hand, then prove it restores:**
   ```bash
   ops/backup/backup-science-bank.sh
   ops/backup/restore-drill.sh --identity /path/to/science-bank-backup-key.txt --from-remote latest
   ```
   Expect `RESULT: PASS`. Delete the key file from disk afterwards.
5. **Schedule it** (copy the units below, then enable). systemd user timers only fire while you are logged out if
   lingering is on for the account: check `loginctl show-user $USER -p Linger` (the Life timers have the same
   requirement).

### Unit files (for you to install; paths assume the repo is at `/home/brandon/apps/science-bank`)

`~/.config/systemd/user/science-bank-backup.service`
```ini
[Unit]
Description=Encrypted offsite backup of the Science Bank database

[Service]
Type=oneshot
ExecStart=/home/brandon/apps/science-bank/ops/backup/backup-science-bank.sh
```

`~/.config/systemd/user/science-bank-backup.timer`
```ini
[Unit]
Description=Daily encrypted offsite backup of the Science Bank database

[Timer]
OnCalendar=*-*-* 03:40:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

`~/.config/systemd/user/science-bank-backup-watchdog.service`
```ini
[Unit]
Description=Dead-man's-switch check for Science Bank backups (alerts if stale)

[Service]
Type=oneshot
ExecStart=/home/brandon/apps/science-bank/ops/backup/check-backup-health.sh --check-remote
```

`~/.config/systemd/user/science-bank-backup-watchdog.timer`
```ini
[Unit]
Description=Run the Science Bank backup watchdog twice daily

[Timer]
OnCalendar=*-*-* 09:10:00
OnCalendar=*-*-* 21:10:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now science-bank-backup.timer science-bank-backup-watchdog.timer
systemctl --user list-timers | grep science-bank
```

The backup runs at 03:40, after the Life backup (03:17), so the two do not compete. The watchdog needs at least
one successful run first, or it will (correctly) alert that nothing has ever been recorded.

## Everyday use

| Want to | Run |
|---|---|
| Take a backup right now | `ops/backup/backup-science-bank.sh` |
| Back up before a deploy or migration | `ops/backup/backup-science-bank.sh --label pre-deploy` |
| Local copy only (no Drive) | `ops/backup/backup-science-bank.sh --no-upload` |
| See what happened | `tail ~/.local/state/science-bank-backup/backup.log`, and `last-run.json` in the same folder |
| Check freshness now | `ops/backup/check-backup-health.sh --check-remote` |
| List remote copies | `rclone lsf gdrive-backup:science-bank-backups` |

State lives in `~/.local/state/science-bank-backup/` (log, lock, last-run.json, success markers).

## Restore drill (do this monthly, and after any change to these scripts)

```bash
ops/backup/restore-drill.sh --identity /path/to/key.txt --from-remote latest
```

A pass means: the file decrypts with your key, every file matches its checksum, `pg_restore` succeeds into a
throwaway Postgres, every table is present, and the schema version matches. Row counts that differ slightly are
reported but do not fail (a teacher may save something while the dump runs); a missing table, an empty table that
had rows, or a schema-version mismatch does fail. The throwaway container is removed afterwards.

## Real restore (disaster recovery)

Try the drill first; a restore you have never rehearsed is a guess.

1. On the target host, get the repo (`git clone`), and recover the files:
   `ops/backup/restore-drill.sh --identity KEY --from-remote latest --extract-to ~/restore`.
   That gives `~/restore/science_bank.dump`, `manifest.json`, and `env`. Copy `env` to `<repo>/.env` (mode 600).
2. Start only the database: `docker compose up -d postgres`, wait until healthy.
3. Load the dump into the empty database:
   ```bash
   docker compose exec -T postgres sh -c \
     'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --exit-on-error' \
     < ~/restore/science_bank.dump
   ```
   Restoring over an existing database instead? Stop the app first (`docker compose stop app`), take a fresh
   `backup-science-bank.sh --no-upload --label before-restore`, and add `--clean --if-exists` to `pg_restore`.
4. `docker compose up -d app` (it runs `alembic upgrade head`, a no-op when the dump is current), then check
   `curl -s localhost:8420/readyz`.
5. Delete `~/restore` (it holds the database and `.env`).

## Key management

- Losing the private key means **no backup can be read**. Keep it in the password manager and confirm you can
  read it there. The restore drill is the proof.
- Use a separate key for Science Bank (this job) from the Life key, so neither exposes the other.
- Rotating: generate a new key, put its public key in `recipients.txt` (you may list several; every backup is
  encrypted to all of them), keep the old private key until the old backups age out (90 days).
- If the server is suspected compromised, the public key alone reveals nothing, but rotate anyway.

## Limits, stated plainly

- **Up to 24 hours of changes can be lost** (daily schedule). Use `--label pre-deploy` before risky changes.
  Point-in-time recovery (WAL archiving) is not set up and is not needed at this size.
- The watchdog sees the job's own markers and, with `--check-remote`, the remote listing. It cannot tell whether
  the backup contents are good; only the restore drill proves that.
- A backup taken while the app is writing is still consistent (one `pg_dump` snapshot), but the manifest's row
  counts are read just after the dump, so they can differ by a write that landed in between. The drill tolerates that.
- Privacy: a backup holds accounts, password hashes and teacher content, and no student names (results are class
  totals). It is encrypted before it leaves the server.

## Tests

```bash
ops/backup/tests/run-tests.sh
```

Needs docker, age, rclone, python3. Uses a scratch Postgres, a throwaway key, a local folder as the "remote" and a
fake notifier, so it never touches production, Drive or ntfy. It covers the happy path, every failure mode
(bad or private key, failed or tiny or non-Postgres dump, failed and truncated uploads, concurrent runs),
retention, the watchdog, the drill (good, wrong key, tampered, damaged, missing table), and extraction.
