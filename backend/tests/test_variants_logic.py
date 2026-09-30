"""Pure rules for variants: content fingerprints and signed preview tokens."""

import pytest

from app.services import variants as v

CHOICES = [
    {"label": "A", "text": "Logistic growth", "correct": True, "rationale": "r1"},
    {"label": "B", "text": "Exponential growth", "correct": False, "rationale": "r2"},
    {"label": "C", "text": "Linear growth", "correct": False, "rationale": "r3"},
]
STIM = {"kind": "survey", "title": "Deer", "tables": [{"rows": [{"year": 1, "n": 10}]}]}


def fp(**over):
    args = {
        "question_type": "multiple_choice",
        "stem": "Which model fits?",
        "choices": CHOICES,
        "answer": "A. Logistic growth",
        "stimulus": STIM,
    }
    args.update(over)
    return v.fingerprint(**args)


def test_reordering_and_relabelling_choices_does_not_change_the_fingerprint():
    shuffled = [
        {"label": "A", "text": "Linear growth", "correct": False, "rationale": "x"},
        {"label": "B", "text": "Logistic growth", "correct": True, "rationale": "y"},
        {"label": "C", "text": "Exponential growth", "correct": False, "rationale": "z"},
    ]
    assert fp(choices=shuffled, answer="B. Logistic growth") == fp()


def test_whitespace_in_the_stem_is_ignored():
    assert fp(stem="  Which   model fits? ") == fp()


@pytest.mark.parametrize(
    "change",
    [
        {"stem": "Which model best fits?"},
        {"question_type": "constructed_response", "choices": [], "answer": "Logistic growth"},
        {"stimulus": {**STIM, "title": "Elk"}},
        {"stimulus": None},
        {"choices": [{**CHOICES[0], "correct": False}, {**CHOICES[1], "correct": True}, CHOICES[2]]},
    ],
)
def test_any_content_change_changes_the_fingerprint(change):
    assert fp(**change) != fp()


def test_different_scenario_with_the_same_answer_is_a_different_fingerprint():
    assert fp(stem="Which model fits the elk data?", stimulus={**STIM, "title": "Elk"}) != fp()


def token(**over):
    args = {
        "user_id": 7,
        "parent_id": 3,
        "parent_version_id": 9,
        "seed": "v-abc-3-0",
        "family_key": "population-carrying-capacity",
        "family_version": "1.0.0",
        "now": 1_000_000,
    }
    args.update(over)
    return v.issue_token(**args)


def test_token_round_trips_and_carries_its_fields():
    t = v.verify_token(token(), user_id=7, now=1_000_100)
    assert (t.parent_id, t.parent_version_id, t.seed, t.family_version) == (3, 9, "v-abc-3-0", "1.0.0")
    assert t.expires_at == 1_000_000 + v.TOKEN_TTL_SECONDS


def test_tokens_have_unique_ids():
    assert (
        v.verify_token(token(), user_id=7, now=1_000_001).token_id
        != v.verify_token(token(), user_id=7, now=1_000_001).token_id
    )


def test_expired_token_is_rejected():
    with pytest.raises(v.TokenError, match="expired"):
        v.verify_token(token(), user_id=7, now=1_000_000 + v.TOKEN_TTL_SECONDS + 1)


def test_another_users_token_is_rejected():
    with pytest.raises(v.TokenError, match="different user"):
        v.verify_token(token(), user_id=8, now=1_000_001)


def test_tampered_payload_or_signature_is_rejected():
    raw, sig = token().split(".")
    flipped = raw[:-1] + ("A" if raw[-1] != "A" else "B")
    with pytest.raises(v.TokenError):
        v.verify_token(f"{flipped}.{sig}", user_id=7, now=1_000_001)
    with pytest.raises(v.TokenError):
        v.verify_token(f"{raw}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}", user_id=7, now=1_000_001)


@pytest.mark.parametrize("bad", ["", "abc", "a.b.c", "."])
def test_malformed_tokens_are_rejected(bad):
    with pytest.raises(v.TokenError):
        v.verify_token(bad, user_id=7, now=1_000_001)


def test_candidate_seed_fits_the_generate_seed_pattern():
    import re

    seed = v.candidate_seed("0123456789abcdef", 123456, 24)
    assert re.fullmatch(r"[A-Za-z0-9._-]{1,64}", seed)
