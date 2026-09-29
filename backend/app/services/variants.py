"""Variant content fingerprints and signed preview tokens. Pure functions; no database access."""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any

TOKEN_TTL_SECONDS = 30 * 60
MAX_BATCH = 20
LINEAGE_CEILING = 50
MAX_ATTEMPTS = 25

_SPACE = re.compile(r"\s+")


def _norm(text: str | None) -> str:
    return _SPACE.sub(" ", text or "").strip()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(
    question_type: str, stem: str, choices: list[dict], answer: str, stimulus: dict[str, Any] | None
) -> str:
    """Identity of a question's content for variant distinctness.

    Answer-choice labels and order are ignored, so a reshuffle cannot pass as a new question. The
    correct answer of a multiple-choice item is taken from its choices, never from the labelled answer
    string. This proves the output differs structurally; it says nothing about difficulty.
    """
    if question_type == "multiple_choice":
        pairs = sorted([_norm(c["text"]), bool(c["correct"])] for c in choices)
        answer_text = next((_norm(c["text"]) for c in choices if c["correct"]), "")
    else:
        pairs = []
        answer_text = _norm(answer)
    payload = {"t": question_type, "s": _norm(stem), "c": pairs, "a": answer_text, "x": stimulus}
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def candidate_seed(nonce: str, parent_id: int, attempt: int) -> str:
    return f"v-{nonce}-{parent_id}-{attempt}"


class TokenError(ValueError):
    """The message is safe to show to the teacher."""


@dataclass(frozen=True)
class CandidateToken:
    token_id: str
    expires_at: int
    user_id: int
    parent_id: int
    parent_version_id: int
    seed: str
    family_key: str
    family_version: str


def _key() -> bytes:
    from app.core.config import get_settings

    return hashlib.sha256(("variant-token:" + get_settings().jwt_secret).encode()).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(raw: str) -> str:
    return _b64(hmac.new(_key(), raw.encode(), hashlib.sha256).digest())


def issue_token(
    *,
    user_id: int,
    parent_id: int,
    parent_version_id: int,
    seed: str,
    family_key: str,
    family_version: str,
    now: int | None = None,
) -> str:
    issued = int(time.time()) if now is None else now
    body = {
        "tid": secrets.token_hex(8),
        "exp": issued + TOKEN_TTL_SECONDS,
        "uid": user_id,
        "pid": parent_id,
        "pvid": parent_version_id,
        "seed": seed,
        "fk": family_key,
        "fv": family_version,
    }
    raw = _b64(_canonical(body).encode())
    return f"{raw}.{_sign(raw)}"


def verify_token(token: str, *, user_id: int, now: int | None = None) -> CandidateToken:
    parts = token.split(".")
    if len(parts) != 2:
        raise TokenError("Malformed candidate token")
    raw, sig = parts
    if not hmac.compare_digest(sig, _sign(raw)):
        raise TokenError("Invalid candidate token")
    try:
        body = json.loads(_unb64(raw))
        parsed = CandidateToken(
            token_id=body["tid"],
            expires_at=int(body["exp"]),
            user_id=int(body["uid"]),
            parent_id=int(body["pid"]),
            parent_version_id=int(body["pvid"]),
            seed=body["seed"],
            family_key=body["fk"],
            family_version=body["fv"],
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise TokenError("Malformed candidate token") from exc
    current = int(time.time()) if now is None else now
    if parsed.expires_at < current:
        raise TokenError("This candidate has expired; preview again")
    if parsed.user_id != user_id:
        raise TokenError("This candidate was created for a different user")
    return parsed
