"""Mutation effects (B-LS3-2): a one-nucleotide change in a gene and what it does to the protein.

Curated data only: the standard genetic code (shared with protein_synthesis). Every key is computed from the original
and changed template strands and the codon table the student sees. Translation always starts at the displayed AUG and
continues in groups of three to the first in-frame Stop; a draw is rejected when any translation an item needs never
meets a Stop, so no item depends on a partial codon. Scope follows the Biology 1 boundary: no meiosis phases, no
biochemical mechanisms, no named genes or proteins, and no naming of silent, missense, or nonsense changes.
"""

from typing import Any

from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily
from app.services.families.protein_synthesis import (
    AMINO_ACIDS,
    CODONS,
    GENE_LABELS,
    SENSE_CODONS,
    START,
    STOP_CODONS,
    codons_of,
    sequence_text,
    strand_text,
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


# ---- family --------------------------------------------------------------------------------

SEQUENCE_MODEL = "Translation starts at the start codon (AUG) and continues in groups of three nucleotides until the first stop codon."
FRAMESHIFT_NOTE = (
    "Adding or removing one nucleotide shifts the way the codons are grouped. This is a frameshift: the codons after "
    "the change are read in a different grouping, so the amino acids after the change are different."
)
_BASE_INTRO = (
    "A mutation is a change in the DNA sequence of a gene. The gene's template strand is transcribed into mRNA, and the "
    "mRNA codons specify the amino acids of a protein."
)
_TABLE_RULE = "Use the codon table shown. You do not need to memorize codons."
_TABLE_KEYS = {"new_protein_after_change", "effect_on_protein", "defend_claim_about_change"}


def _is_indel(edit: dict[str, Any]) -> bool:
    return edit["type"] != "substitution"


def _frameshift(text: str, edit: dict[str, Any]) -> str:
    return f"{text} {FRAMESHIFT_NOTE}" if _is_indel(edit) else text


def _edit_sentence(edit: dict[str, Any]) -> str:
    if edit["type"] == "substitution":
        return f"nucleotide {edit['position']} was changed from {edit['old']} to {edit['new']}"
    if edit["type"] == "deletion":
        return f"nucleotide {edit['position']} ({edit['old']}) was removed"
    return f"the nucleotide {edit['new']} was added between nucleotide {edit['position']} and nucleotide {edit['position'] + 1}"


def _strands_sentence(role: dict[str, Any]) -> str:
    return (
        f"Original template strand: {strand_text(role['original']['template'], '3', '5')}. "
        f"Changed template strand: {strand_text(role['changed']['template'], '3', '5')}."
    )


class MutationEffects(QuestionFamily):
    key = "mutation-effects"
    version = "1.0.0"
    title = "Mutations: effects on a protein"
    description = (
        "Compare an original and a changed DNA template strand: identify the substitution, insertion, or deletion, find "
        "the protein made from the changed gene with a displayed codon table, describe its effect, decide whether a "
        "mutation can be inherited, and defend a claim about what the change did."
    )
    stimulus_kind = "mutation_effects"
    bindings = (Binding("SC", "biology-1", "B-LS3-2"),)
    templates = (
        TemplateSpec("identify_mutation_type", "Identify the kind of mutation", 1, "multiple_choice", "evidence", 1),
        TemplateSpec(
            "new_protein_after_change", "Protein made from the changed gene", 2, "multiple_choice", "reasoning", 0
        ),
        TemplateSpec("effect_on_protein", "Effect of a mutation on a protein", 2, "multiple_choice", "reasoning", 0),
        TemplateSpec("inheritance_of_mutation", "Can a mutation be inherited?", 2, "multiple_choice", "reasoning", 1),
        TemplateSpec(
            "defend_claim_about_change",
            "Make and defend a claim about a mutation",
            3,
            "constructed_response",
            "reasoning",
            2,
        ),
    )

    # ---- scenario and stimulus --------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        keys = set(template_keys)
        intro = [_BASE_INTRO]
        tables = []
        if keys & _TABLE_KEYS:
            intro += [SEQUENCE_MODEL, _TABLE_RULE]
            tables.append(
                {
                    "caption": "Codon table (mRNA codons, read 5′ to 3′)",
                    "columns": [{"key": "codon", "label": "mRNA codon"}, {"key": "amino_acid", "label": "Amino acid"}],
                    "rows": params["codon_table"],
                }
            )
        return {
            "title": "Mutations and proteins",
            "intro": " ".join(intro),
            "sections": [],
            "tables": tables,
            "charts": [],
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_identify_mutation_type(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        role = params["roles"]["classify"]
        edit = role["edit"]
        texts = {
            "substitution": "A substitution: one nucleotide was replaced by another.",
            "insertion": "An insertion: one nucleotide was added.",
            "deletion": "A deletion: one nucleotide was removed.",
        }
        why_not = {
            ("substitution", "insertion"): "The strands have the same number of nucleotides, so none was added.",
            ("substitution", "deletion"): "The strands have the same number of nucleotides, so none was removed.",
            (
                "insertion",
                "substitution",
            ): "The strands are different lengths, so a nucleotide was added, not just replaced.",
            ("insertion", "deletion"): "The changed strand is longer, so a nucleotide was added, not removed.",
            (
                "deletion",
                "substitution",
            ): "The strands are different lengths, so a nucleotide was removed, not just replaced.",
            ("deletion", "insertion"): "The changed strand is shorter, so a nucleotide was removed, not added.",
        }
        choices = []
        for kind, text in texts.items():
            if kind == edit["type"]:
                why = f"Correct: comparing the strands, {_edit_sentence(edit)}."
            else:
                why = why_not[(edit["type"], kind)]
            choices.append(DraftChoice(text, kind == edit["type"], _frameshift(why, edit)))
        choices.append(
            DraftChoice(
                "No mutation occurred, because the protein is not changed.",
                False,
                _frameshift(
                    "The DNA sequence changed, so a mutation occurred. A mutation is a change in the DNA sequence, "
                    "whether or not the protein changes.",
                    edit,
                ),
            )
        )
        correct = texts[edit["type"]]
        return DraftQuestion(
            stem=(
                f"The DNA of a cell was changed by {params['cause']}. The template strands of {role['label']} before "
                f"and after the change are shown. {_strands_sentence(role)} Which statement describes the change?"
            ),
            answer=correct,
            explanation=_frameshift(
                f"Comparing the strands, {_edit_sentence(edit)}, so this is a {edit['type']}.", edit
            ),
            choices=choices,
        )

    def _q_new_protein_after_change(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        role = params["roles"]["protein"]
        edit = role["edit"]
        original, changed = role["original"]["protein"], role["changed"]["protein"]
        options = role["distractors"]
        correct = sequence_text(changed)
        why = {
            "original": "This is the protein made from the original strand. The changed strand is read codon by codon, and it makes a different protein.",
            "site_left_out": "This leaves out the amino acid at the change instead of reading the changed strand codon by codon.",
            "misread": "This reads the DNA template strand directly as if it were mRNA. The template must first be transcribed into its complementary mRNA.",
        }
        choices = [
            DraftChoice(
                correct,
                True,
                _frameshift(
                    "Correct: the changed strand is transcribed into mRNA, and the mRNA is read from the start codon to "
                    "the first stop codon using the table.",
                    edit,
                ),
            )
        ] + [
            DraftChoice(sequence_text(options[k]), False, _frameshift(why[k], edit))
            for k in ("original", "site_left_out", "misread")
        ]
        return DraftQuestion(
            stem=(
                f"A mutation changed the DNA template strand of {role['label']}. {_strands_sentence(role)} "
                f"{SEQUENCE_MODEL} Use the codon table to find the amino acid sequence made from the changed gene."
            ),
            answer=correct,
            explanation=_frameshift(
                f"The original protein is {sequence_text(original)}. The changed strand is transcribed into "
                f"{role['changed']['mrna']} and read to the first stop codon, which gives {correct}.",
                edit,
            ),
            choices=choices,
        )

    def _q_effect_on_protein(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        role = params["roles"]["effect"]
        edit, category = role["edit"], role["category"]
        original, changed = role["original"]["protein"], role["changed"]["protein"]
        before, after = sequence_text(original), sequence_text(changed)
        right = {
            "unchanged": f"Correct: both strands give {before}. The changed codon still specifies the same amino acid.",
            "one_changed": (
                f"Correct: the original protein is {before} and the changed protein is {after}. Only one amino acid "
                "differs."
            ),
            "ends_early": (
                f"Correct: the changed protein is {after}. A new stop codon is read, so the protein ends after "
                f"{len(changed)} amino acids instead of {len(original)}."
            ),
            "several_differ": (
                f"Correct: the original protein is {before} and the changed protein is {after}. Several amino acids "
                "after the change are different."
            ),
        }
        choices = []
        for name, text in EFFECT_TEXT.items():
            if name == category:
                why = right[name]
            else:
                why = (
                    f"Not supported: the original protein is {before} and the changed protein is {after}, which does "
                    "not match this statement."
                )
            choices.append(DraftChoice(text, name == category, _frameshift(why, edit)))
        return DraftQuestion(
            stem=(
                f"A mutation changed the DNA template strand of {role['label']}. {_strands_sentence(role)} "
                f"{SEQUENCE_MODEL} Use the codon table to compare the original and changed proteins. Which statement "
                "describes how the change affects the protein?"
            ),
            answer=EFFECT_TEXT[category],
            explanation=_frameshift(
                f"The original protein is {before}. The changed protein is {after}. {EFFECT_TEXT[category]}", edit
            ),
            choices=choices,
        )

    def _q_inheritance_of_mutation(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        info = params["inheritance"]
        organism, cell, mutagen = info["organism"], info["cell"], info["mutagen"]
        if info["gamete"]:
            word = cell.split(" ", 1)[1]
            correct = f"The mutation can be inherited by offspring if the changed {word} takes part in fertilization."
            right = (
                "Correct: a mutation in a gamete is in the genetic material that offspring receive when that gamete "
                "takes part in fertilization."
            )
            opposite = "The mutation will not be passed to offspring, because only body cells can carry mutations."
            opposite_why = "Gametes carry genetic material to offspring, so a mutation in a gamete can be inherited."
        else:
            correct = (
                "The mutation will not be passed to offspring, but cells that come from the changed body cell will "
                "carry it."
            )
            right = (
                "Correct: a mutation in a body cell stays in the cells that come from it. It is not in the gametes, so "
                "offspring do not receive it."
            )
            opposite = "The mutation will be passed to all offspring, because every mutation is inherited."
            opposite_why = (
                "Only mutations in gametes can be passed to offspring. A body cell mutation is not in the gametes."
            )
        choices = [
            DraftChoice(correct, True, right),
            DraftChoice(opposite, False, opposite_why),
            DraftChoice(
                f"The mutation will appear in every cell of {organism} and in all of its offspring.",
                False,
                "A mutation starts in one cell and is only in the cells that come from it, so it is not in every cell.",
            ),
            DraftChoice(
                f"{mutagen[0].upper()}{mutagen[1:]} cannot cause a mutation; only copying errors during replication "
                "change DNA.",
                False,
                "A mutagen, such as ultraviolet light or X-rays, is an environmental factor that can change DNA.",
            ),
        ]
        return DraftQuestion(
            stem=(
                f"{organism[0].upper()}{organism[1:]} is exposed to {mutagen}, a mutagen. The exposure causes a "
                f"mutation in the DNA of {cell}. Which statement is supported?"
            ),
            answer=correct,
            explanation=right,
            choices=choices,
        )

    def _q_defend_claim_about_change(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        role = params["roles"]["claim"]
        edit, category = role["edit"], role["category"]
        original, changed = role["original"]["protein"], role["changed"]["protein"]
        effect = {
            "unchanged": "does not change the protein",
            "one_changed": "changes one amino acid in the protein",
            "ends_early": "makes the protein end early",
            "several_differ": "changes several amino acids after the change",
        }[category]
        counterclaim = (
            "Every change in the DNA sequence changes the protein."
            if category == "unchanged"
            else "A change of one nucleotide cannot change the protein."
        )
        rebuttal = (
            "The counterclaim is wrong: although the DNA sequence changed, the changed codon still specifies the same "
            "amino acid in the table, so this change did not alter the protein."
            if category == "unchanged"
            else "The counterclaim is wrong: the evidence shows that changing one nucleotide produced a different protein."
        )
        answer = (
            f"Claim: this {edit['type']} ({_edit_sentence(edit)}) {effect}. "
            f"Evidence: the original template strand {strand_text(role['original']['template'], '3', '5')} is "
            f"transcribed into the mRNA {strand_text(role['original']['mrna'], '5', '3')}, which the table translates as "
            f"{sequence_text(original)}. The changed template strand {strand_text(role['changed']['template'], '3', '5')} "
            f"is transcribed into {strand_text(role['changed']['mrna'], '5', '3')}, which the table translates as "
            f"{sequence_text(changed)}. "
            "Reasoning: a change in the DNA sequence changes the mRNA codons, and the codons set the amino acid sequence, "
            "so a mutation can produce a protein that differs between cells or organisms. "
            f"{rebuttal}"
        )
        return DraftQuestion(
            stem=(
                f"A mutation changed the DNA template strand of {role['label']}. {_strands_sentence(role)} "
                f"{SEQUENCE_MODEL} Make a claim about what the change did to the protein, and defend it with evidence "
                "from the displayed strands and codon table, and the derived amino acid sequences. A classmate says: "
                f'"{counterclaim}" Explain how your evidence answers this counterclaim.'
            ),
            answer=_frameshift(answer, edit),
            explanation=_frameshift(
                "Scoring guide (4 points): (1) a claim that names the type of change and its effect on the protein; "
                "(2) evidence from the displayed strands and codon table, and the derived amino acid sequences; "
                "(3) reasoning that the changed DNA changes the mRNA codons, which can change the amino acids and so "
                "produce genetic variation; (4) an answer to the counterclaim that uses the evidence.",
                edit,
            ),
        )
