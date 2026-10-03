"""Mutation effects (B-LS3-2): a one-nucleotide change in a gene and what it does to the protein.

Curated data only: the standard genetic code (shared with protein_synthesis). Every key is computed from the original
and changed template strands and the codon table the student sees. Translation always starts at the displayed AUG and
continues in groups of three to the first in-frame Stop; a draw is rejected when any translation an item needs never
meets a Stop, so no item depends on a partial codon. Scope follows the Biology 1 boundary: no meiosis phases, no
biochemical mechanisms, no named genes or proteins, and no naming of silent, missense, or nonsense changes.
"""

from typing import Any

from app.services.engine.core import GenerationError, Rng
from app.services.families.protein_synthesis import (
    AMINO_ACIDS,
    CODONS,
    GENE_LABELS,
    SENSE_CODONS,
    START,
    STOP_CODONS,
    codons_of,
    table_label,
    template_for,
    transcribe,
)

MAX_DRAWS = 400
ALL_CODONS = tuple(sorted(CODONS))
EDIT_KINDS = ("substitution", "insertion", "deletion")
CATEGORY_KINDS = {
    "unchanged": ("substitution",),
    "one_changed": ("substitution",),
    "ends_early": ("substitution",),
    "several_differ": ("insertion", "deletion"),
}
EFFECT_TEXT = {
    "unchanged": "The protein is unchanged.",
    "one_changed": "Exactly one amino acid is different.",
    "ends_early": "The protein ends early, because a new stop codon is read.",
    "several_differ": "Several amino acids after the change are different.",
}
CAUSES = (
    "a copying error during DNA replication",
    "exposure to ultraviolet light, a mutagen",
    "exposure to X-rays, a mutagen",
)
ORGANISMS = ("a mouse", "a fruit fly", "a zebrafish")
CELLS = ("a body cell (somatic cell)", "an egg cell", "a sperm cell")
MUTAGENS = ("ultraviolet light", "X-rays")


# ---- reading and classifying ---------------------------------------------------------------


def read_protein(mrna: str) -> tuple[list[str] | None, list[str]]:
    """Amino acid names from the start codon to the first in-frame Stop, and the codons read (Stop included).

    Returns `None` for the names when no Stop is met within the full codons shown (a partial last codon is ignored).
    """
    names: list[str] = []
    used: list[str] = []
    for codon in codons_of(mrna[: len(mrna) - len(mrna) % 3]):
        used.append(codon)
        if CODONS[codon] == "*":
            return names, used
        names.append(AMINO_ACIDS[CODONS[codon]])
    return None, used


def effect_flags(original: list[str], changed: list[str]) -> dict[str, bool]:
    """Four predicates over the original and changed proteins. They are pairwise disjoint."""
    differing = sum(a != b for a, b in zip(original, changed))
    return {
        "unchanged": changed == original,
        "one_changed": len(changed) == len(original) and differing == 1,
        "ends_early": len(changed) < len(original) and changed == original[: len(changed)],
        "several_differ": len(changed) >= len(original) and differing >= 2,
    }


def effect_of(original: list[str], changed: list[str]) -> str | None:
    """The one true category, or None when no description is true (such a draw is rejected)."""
    true = [name for name, value in effect_flags(original, changed).items() if value]
    return true[0] if len(true) == 1 else None


def _all_distinct(options: list[list[str]]) -> bool:
    return len({tuple(o) for o in options}) == len(options)


# ---- edits and genes -----------------------------------------------------------------------


def make_edit(rng: Rng, template: str, n_sense: int, kind: str) -> dict[str, Any] | None:
    """One edit inside the sense codons, or None when an indel's position would be ambiguous."""
    index = rng.randint(3, 3 * (n_sense + 1) - 1)
    if kind == "substitution":
        new = rng.choice([b for b in "ACGT" if b != template[index]])
        changed = template[:index] + new + template[index + 1 :]
        return {
            "type": kind,
            "index": index,
            "position": index + 1,
            "old": template[index],
            "new": new,
            "changed": changed,
        }
    if kind == "deletion":
        if template[index] in (template[index - 1], template[index + 1]):
            return None
        changed = template[:index] + template[index + 1 :]
        return {
            "type": kind,
            "index": index,
            "position": index + 1,
            "old": template[index],
            "new": None,
            "changed": changed,
        }
    new = rng.choice("ACGT")
    if new in (template[index - 1], template[index]):
        return None
    changed = template[:index] + new + template[index:]
    return {"type": kind, "index": index, "position": index, "old": None, "new": new, "changed": changed}


def draw_gene(rng: Rng) -> dict[str, Any]:
    n_sense = rng.randint(3, 4)
    sense = [rng.choice(SENSE_CODONS) for _ in range(n_sense)]
    coding = [START, *sense, rng.choice(STOP_CODONS)]
    tail = [rng.choice(ALL_CODONS) for _ in range(rng.randint(4, 5))]
    mrna = "".join(coding + tail)
    return {"n_sense": n_sense, "mrna": mrna, "template": template_for(mrna)}


def draw_role(
    rng: Rng, label: str, *, category: str | None = None, translate: bool = True, distractors: bool = False
) -> dict[str, Any]:
    kinds = CATEGORY_KINDS[category] if category else EDIT_KINDS
    for _ in range(MAX_DRAWS):
        gene = draw_gene(rng)
        edit = make_edit(rng, gene["template"], gene["n_sense"], rng.choice(kinds))
        if edit is None:
            continue
        changed_template = edit.pop("changed")
        role: dict[str, Any] = {
            "label": label,
            "n_sense": gene["n_sense"],
            "original": {"template": gene["template"], "mrna": gene["mrna"], "protein": None},
            "changed": {"template": changed_template, "mrna": transcribe(changed_template), "protein": None},
            "edit": edit,
            "category": None,
            "codons_read": [],
        }
        if not translate:
            return role
        original, read_original = read_protein(role["original"]["mrna"])
        changed, read_changed = read_protein(role["changed"]["mrna"])
        if original is None or changed is None:
            continue
        found = effect_of(original, changed)
        if found is None or (found == "several_differ") != (edit["type"] != "substitution"):
            continue
        if category is not None and found != category:
            continue
        used = set(read_original) | set(read_changed)
        if distractors:
            misread, read_misread = read_protein(changed_template.replace("T", "U"))
            if misread is None:
                continue
            site = edit["index"] // 3
            options = {
                "original": original,
                "site_left_out": original[:site] + original[site + 1 :],
                "misread": misread,
            }
            if not _all_distinct([changed, *options.values()]):
                continue
            role["distractors"] = options
            used |= set(read_misread)
        role["original"]["protein"], role["changed"]["protein"] = original, changed
        role["category"] = found
        role["codons_read"] = sorted(used)
        return role
    raise GenerationError(f"mutation-effects: no valid {label} scenario after {MAX_DRAWS} draws")


def draw_scenario(rng: Rng) -> dict[str, Any]:
    labels = rng.sample(list(GENE_LABELS), 4)
    roles = {
        "classify": draw_role(rng, labels[0], translate=False),
        "protein": draw_role(rng, labels[1], distractors=True),
        "effect": draw_role(rng, labels[2], category=rng.choice(list(EFFECT_TEXT))),
        "claim": draw_role(rng, labels[3]),
    }
    needed: set[str] = set()
    for name in ("protein", "effect", "claim"):
        needed |= set(roles[name]["codons_read"])
    extras = rng.sample(sorted(set(SENSE_CODONS) - needed), rng.randint(2, 3))
    cell = rng.choice(CELLS)
    return {
        "roles": roles,
        "cause": rng.choice(CAUSES),
        "inheritance": {
            "organism": rng.choice(ORGANISMS),
            "cell": cell,
            "gamete": cell != CELLS[0],
            "mutagen": rng.choice(MUTAGENS),
        },
        "codon_table": [{"codon": c, "amino_acid": table_label(c)} for c in sorted(needed | set(extras))],
    }
