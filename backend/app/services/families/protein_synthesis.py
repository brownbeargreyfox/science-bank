"""DNA to protein (B-LS1-1): transcribe a template strand and translate the mRNA with a displayed codon table.

Curated data only: the standard genetic code. Every key is computed from the strands and table the student sees.
Scope follows the Biology 1 boundary: no initiation, elongation or termination steps, no named genes or proteins, and
no effects of sequence changes (those belong to B-LS3-2).
"""

from itertools import product
from typing import Any

from app.services.engine.core import Binding, DraftChoice, DraftQuestion, GenerationError, Rng, TemplateSpec
from app.services.engine.family import QuestionFamily

# Standard genetic code. Codons are enumerated with U, C, A, G in each position; "*" marks a stop codon.
_CODE = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
AMINO_ACIDS = {
    "F": "Phenylalanine",
    "L": "Leucine",
    "S": "Serine",
    "Y": "Tyrosine",
    "C": "Cysteine",
    "W": "Tryptophan",
    "P": "Proline",
    "H": "Histidine",
    "Q": "Glutamine",
    "R": "Arginine",
    "I": "Isoleucine",
    "M": "Methionine",
    "T": "Threonine",
    "N": "Asparagine",
    "K": "Lysine",
    "V": "Valine",
    "A": "Alanine",
    "D": "Aspartic acid",
    "E": "Glutamic acid",
    "G": "Glycine",
}
CODONS: dict[str, str] = {"".join(bases): _CODE[i] for i, bases in enumerate(product("UCAG", repeat=3))}
START = "AUG"
SENSE_CODONS = tuple(sorted(c for c, x in CODONS.items() if x != "*" and c != START))
STOP_CODONS = tuple(sorted(c for c, x in CODONS.items() if x == "*"))

_MRNA_TO_TEMPLATE = {"A": "T", "U": "A", "G": "C", "C": "G"}
_TEMPLATE_TO_MRNA = {"A": "U", "T": "A", "G": "C", "C": "G"}
_TEMPLATE_COMPLEMENT = {"A": "T", "T": "A", "G": "C", "C": "G"}
GENE_LABELS = ("Gene R2", "Gene K7", "Gene M4", "Gene T9", "Gene L3", "Gene H5")
ACTIVITY_GENES = ("Gene A", "Gene B", "Gene C", "Gene D")
MAX_GENE_DRAWS = 200


# ---- pure helpers ------------------------------------------------------------------------------


def transcribe(template: str) -> str:
    return "".join(_TEMPLATE_TO_MRNA[b] for b in template)


def template_for(mrna: str) -> str:
    return "".join(_MRNA_TO_TEMPLATE[b] for b in mrna)


def codons_of(strand: str) -> list[str]:
    return [strand[i : i + 3] for i in range(0, len(strand), 3)]


def translate(codons: list[str]) -> list[str]:
    """Amino acid names in order; a stop codon ends the chain and is not an amino acid."""
    names = []
    for codon in codons:
        letter = CODONS[codon]
        if letter == "*":
            break
        names.append(AMINO_ACIDS[letter])
    return names


def table_label(codon: str) -> str:
    if CODONS[codon] == "*":
        return "Stop"
    if codon == START:
        return "Methionine (start)"
    return AMINO_ACIDS[CODONS[codon]]


def strand_text(seq: str, left: str, right: str, ends: bool = True) -> str:
    return f"{left}′-{seq}-{right}′" if ends else seq


def transcribe_candidates(gene: dict[str, Any]) -> list[tuple[str, str]]:
    """Wrong mRNA strings a student might choose, each distinct from the key and from each other."""
    key, template = gene["mrna"], gene["template"]
    raw = [
        ("later_codons_copied", key[:3] + template[3:].replace("T", "U")),
        ("dna_complement", "".join(_TEMPLATE_COMPLEMENT[b] for b in template)),
        ("copied", template.replace("T", "U")),
        ("reversed", key[::-1]),
        ("gc_unchanged", "".join(b if b in "GC" else _TEMPLATE_TO_MRNA[b] for b in template)),
    ]
    seen = {key}
    out = []
    for kind, strand in raw:
        if strand not in seen:
            seen.add(strand)
            out.append((kind, strand))
    return out


def _swapped(protein: list[str]) -> list[str]:
    return [protein[0], protein[2], protein[1], *protein[3:]]


def protein_options(gene: dict[str, Any]) -> dict[str, list[str]]:
    p = gene["protein"]
    options = {"reversed": p[::-1], "no_start": p[1:], "swapped": _swapped(p)}
    if "template" in gene:
        options["template_as_mrna"] = translate(codons_of(gene["template"].replace("T", "U")))
    return options


def _distinct(options: list[list[str]]) -> bool:
    return len({tuple(o) for o in options}) == len(options)


def transcribe_gene_ok(gene: dict[str, Any]) -> bool:
    return len(transcribe_candidates(gene)) >= 3


def translate_gene_ok(gene: dict[str, Any]) -> bool:
    o = protein_options(gene)
    return _distinct([gene["protein"], o["reversed"], o["no_start"], o["swapped"]])


def protein_gene_ok(gene: dict[str, Any]) -> bool:
    misread = codons_of(gene["template"].replace("T", "U"))
    if any(CODONS[c] == "*" for c in misread):
        return False
    o = protein_options(gene)
    return _distinct([gene["protein"], o["template_as_mrna"], o["reversed"], o["swapped"]])


# ---- scenario ----------------------------------------------------------------------------------


def draw_gene(rng: Rng, label: str) -> dict[str, Any]:
    sense = [rng.choice(SENSE_CODONS) for _ in range(rng.randint(3, 5))]
    codons = [START, *sense, rng.choice(STOP_CODONS)]
    mrna = "".join(codons)
    return {
        "label": label,
        "codons": codons,
        "mrna": mrna,
        "template": template_for(mrna),
        "protein": translate(codons),
    }


def draw_scenario(rng: Rng) -> dict[str, Any]:
    labels = rng.sample(list(GENE_LABELS), 3)
    genes: dict[str, dict[str, Any]] = {}
    for role, label, ok in (
        ("transcribe", labels[0], transcribe_gene_ok),
        ("translate", labels[1], translate_gene_ok),
        ("protein", labels[2], protein_gene_ok),
    ):
        for _ in range(MAX_GENE_DRAWS):
            gene = draw_gene(rng, label)
            if ok(gene):
                genes[role] = gene
                break
        else:
            raise GenerationError(f"dna-protein-synthesis: no valid {role} gene after {MAX_GENE_DRAWS} draws")
    misread = codons_of(genes["protein"]["template"].replace("T", "U"))
    needed = set(genes["translate"]["codons"]) | set(genes["protein"]["codons"]) | set(misread)
    extras = rng.sample(sorted(set(SENSE_CODONS) - needed), rng.randint(2, 3))
    categories = rng.shuffled(["p_only", "q_only", "both", "neither"])
    activity = [
        {"gene": gene, "p": cat in ("p_only", "both"), "q": cat in ("q_only", "both")}
        for gene, cat in zip(ACTIVITY_GENES, categories, strict=True)
    ]
    return {
        "genes": genes,
        "codon_table": [{"codon": c, "amino_acid": table_label(c)} for c in sorted(needed | set(extras))],
        "activity": activity,
    }


# ---- family ------------------------------------------------------------------------------------

_BASE_INTRO = (
    "A gene is a region of DNA that contains instructions for an amino-acid sequence (a protein). A cell uses one "
    "strand of a gene, the template strand, as a pattern to build messenger RNA (mRNA) by transcription. At a ribosome, the mRNA is read "
    "in groups of three nucleotides called codons, and each codon specifies an amino acid. This is translation."
)
_TABLE_RULE = "Use the codon table shown. You do not need to memorize codons."
_SEQUENCE_KEYS = {"translate_mrna", "dna_to_protein", "explain_dna_to_protein"}

_TRANSCRIBE_WHY = {
    "dna_complement": "RNA contains uracil (U) instead of thymine (T), so a template A pairs with U, not T.",
    "copied": "This copies the template strand instead of pairing each base with its complement.",
    "reversed": (
        "The bases are in the wrong order: each mRNA base pairs with the template base directly across from it, in the "
        "same left-to-right position."
    ),
    "gc_unchanged": "G pairs with C and C pairs with G; this strand leaves the G and C bases unchanged.",
    "later_codons_copied": (
        "The first codon is paired correctly, but the rest of the template strand is copied instead of paired with its "
        "complement."
    ),
}
_PROTEIN_WHY = {
    "reversed": "The amino acids are in reverse order. Codons are read in order from the 5′ end of the mRNA.",
    "no_start": (
        "Translation begins at the start codon, AUG, which specifies methionine. Methionine is the first amino acid."
    ),
    "swapped": "Two amino acids are in the wrong order. Each codon is read in order from the 5′ end of the mRNA.",
    "template_as_mrna": (
        "This reads the DNA template strand directly as if it were mRNA. The template must first be transcribed into its "
        "complementary mRNA."
    ),
}
_PROTEIN_WHY_EOCEP = {
    **_PROTEIN_WHY,
    "reversed": "The amino acids are in reverse order. Codons are read in order from the first codon, at the left end of the mRNA.",
    "swapped": "Two amino acids are in the wrong order. Each codon is read in order from the first codon, at the left end of the mRNA.",
}


CATEGORY_TEXT = {
    "p_only": "active in cell type P only",
    "q_only": "active in cell type Q only",
    "both": "active in both cell types",
    "neither": "not active in either cell type",
}


def activity_category(row: dict[str, Any]) -> str:
    return {(True, False): "p_only", (False, True): "q_only", (True, True): "both", (False, False): "neither"}[
        (row["p"], row["q"])
    ]


def sequence_text(names: list[str]) -> str:
    return " → ".join(names)


class DnaProteinSynthesis(QuestionFamily):
    key = "dna-protein-synthesis"
    version = "1.0.0"
    title = "DNA to protein: transcription and translation"
    description = (
        "Use a DNA template strand and a displayed codon table to transcribe an mRNA, translate it into an amino acid "
        "sequence, and explain how the order of nucleotides in a gene determines the protein."
    )
    stimulus_kind = "dna_protein_synthesis"
    eocep_aware = True
    bindings = (Binding("SC", "biology-1", "B-LS1-1"),)
    templates = (
        TemplateSpec("transcribe_mrna", "Transcribe a template strand", 1, "multiple_choice", "evidence", 4),
        TemplateSpec("translate_mrna", "Translate an mRNA", 1, "multiple_choice", "evidence", 5),
        TemplateSpec("dna_to_protein", "From a template strand to a protein", 2, "multiple_choice", "evidence", 2),
        TemplateSpec(
            "explain_dna_to_protein",
            "Explain how DNA determines a protein",
            3,
            "constructed_response",
            "articulating_explanation",
            0,
        ),
        TemplateSpec("gene_activity_by_cell", "Genes in two cell types", 2, "multiple_choice", "reasoning", 3),
    )

    # ---- scenario and stimulus --------------------------------------------------------------

    def build_scenario(self, rng: Rng) -> dict[str, Any]:
        return draw_scenario(rng)

    def render_stimulus(self, params: dict[str, Any], template_keys: list[str]) -> dict[str, Any]:
        keys = set(template_keys)
        intro = [_BASE_INTRO]
        tables = []
        if keys & _SEQUENCE_KEYS:
            intro.append(_TABLE_RULE)
            tables.append(
                {
                    "caption": "Codon table (mRNA codons)"
                    if params.get("eocep")
                    else "Codon table (mRNA codons, read 5′ to 3′)",
                    "columns": [{"key": "codon", "label": "mRNA codon"}, {"key": "amino_acid", "label": "Amino acid"}],
                    "rows": params["codon_table"],
                }
            )
        if "gene_activity_by_cell" in keys:
            intro.append(
                "Cell types P and Q come from the same organism and contain the same DNA. A gene is active in a cell "
                "when the cell uses it to make a protein."
            )
            tables.append(
                {
                    "caption": "Gene activity in two cell types",
                    "columns": [
                        {"key": "gene", "label": "Gene"},
                        {"key": "p", "label": "Cell type P"},
                        {"key": "q", "label": "Cell type Q"},
                    ],
                    "rows": [
                        {
                            "gene": r["gene"],
                            "p": "Active" if r["p"] else "Not active",
                            "q": "Active" if r["q"] else "Not active",
                        }
                        for r in params["activity"]
                    ],
                }
            )
        return {
            "title": "From DNA to protein",
            "intro": " ".join(intro),
            "sections": [],
            "tables": tables,
            "charts": [],
        }

    # ---- items ------------------------------------------------------------------------------

    def build_question(self, template: TemplateSpec, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        return getattr(self, f"_q_{template.key}")(params, rng)

    def _q_transcribe_mrna(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        g = params["genes"]["transcribe"]
        ends = not params.get("eocep")
        correct = strand_text(g["mrna"], "5", "3", ends)
        candidates = transcribe_candidates(g)
        if params.get("eocep"):
            # Without strand-end labels, the reversed molecule would invite a second, convention-based reading.
            candidates = [candidate for candidate in candidates if candidate[0] != "reversed"]
        # One wrong answer always starts with the correct AUG, so the start codon alone never gives the key away.
        forced = [c for c in candidates if c[0] == "later_codons_copied"]
        wrong = forced + rng.sample([c for c in candidates if c[0] != "later_codons_copied"], 3 - len(forced))
        choices = [
            DraftChoice(
                correct,
                True,
                "Correct: transcription pairs each template base with its complement (A–U, T–A, G–C, C–G).",
            )
        ] + [DraftChoice(strand_text(strand, "5", "3", ends), False, _TRANSCRIBE_WHY[kind]) for kind, strand in wrong]
        if ends:
            stem = (
                f"The DNA template strand of {g['label']} is {strand_text(g['template'], '3', '5')}. Which mRNA, "
                "written 5′ to 3′, is transcribed from this template strand?"
            )
        else:
            stem = (
                f"The DNA template strand of {g['label']} is {g['template']}, read from left to right. Which mRNA, "
                "written from left to right, is transcribed from this template strand?"
            )
        return DraftQuestion(
            stem=stem,
            answer=correct,
            explanation=(
                f"Each template base pairs with its complement (A–U, T–A, G–C, C–G), so {g['template']} is "
                f"transcribed into {g['mrna']}."
            ),
            choices=choices,
        )

    def _q_translate_mrna(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        g = params["genes"]["translate"]
        why = _PROTEIN_WHY_EOCEP if params.get("eocep") else _PROTEIN_WHY
        options = protein_options(g)
        correct = sequence_text(g["protein"])
        choices = [
            DraftChoice(
                correct,
                True,
                "Correct: the codons are read in order from the start codon, and each specifies the amino acid shown "
                "in the table.",
            )
        ] + [DraftChoice(sequence_text(options[k]), False, why[k]) for k in ("reversed", "no_start", "swapped")]
        mrna = f"{g['mrna']}, read from left to right" if params.get("eocep") else strand_text(g["mrna"], "5", "3")
        return DraftQuestion(
            stem=(
                f"The mRNA transcribed from {g['label']} is {mrna}. Translation starts at "
                "the start codon (AUG) and ends at a stop codon. Use the codon table to find the amino acid sequence "
                "this mRNA codes for."
            ),
            answer=correct,
            explanation=(
                f"Reading the codons {', '.join(g['codons'])} with the table gives {correct}; the stop codon "
                f"({g['codons'][-1]}) ends the chain."
            ),
            choices=choices,
        )

    def _q_dna_to_protein(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        g = params["genes"]["protein"]
        why = _PROTEIN_WHY_EOCEP if params.get("eocep") else _PROTEIN_WHY
        options = protein_options(g)
        correct = sequence_text(g["protein"])
        choices = [
            DraftChoice(
                correct,
                True,
                "Correct: the template is transcribed into mRNA, and the mRNA codons are translated with the table.",
            )
        ] + [DraftChoice(sequence_text(options[k]), False, why[k]) for k in ("template_as_mrna", "reversed", "swapped")]
        template = (
            f"{g['template']}, read from left to right" if params.get("eocep") else strand_text(g["template"], "3", "5")
        )
        return DraftQuestion(
            stem=(
                f"The DNA template strand of {g['label']} is {template}. The gene is "
                "transcribed into mRNA, and the mRNA is translated using the codon table shown. Which amino acid "
                "sequence does this gene produce?"
            ),
            answer=correct,
            explanation=(
                f"Transcription gives the mRNA {g['mrna']}. Its codons ({', '.join(g['codons'])}) specify {correct}; "
                "the stop codon ends the chain."
            ),
            choices=choices,
        )

    def _q_explain_dna_to_protein(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        g = params["genes"]["protein"]
        protein = sequence_text(g["protein"])
        return DraftQuestion(
            stem=(
                f"Use the codon table to explain how the DNA template strand of {g['label']}, "
                f"{strand_text(g['template'], '3', '5')}, determines the amino acid sequence of its protein. In your "
                "explanation, write the mRNA that is transcribed (5′ to 3′) and the amino acid sequence that is "
                "produced."
            ),
            answer=(
                f"Transcription builds an mRNA by pairing each template base with its complement (A–U, T–A, G–C, C–G), so "
                f"{strand_text(g['template'], '3', '5')} is transcribed into {strand_text(g['mrna'], '5', '3')}. The "
                f"mRNA is read in codons ({', '.join(g['codons'])}), and the table shows the amino acid each codon "
                f"specifies: {protein}; the stop codon ends the chain. The order of amino acids is the protein's "
                "sequence, so the order of nucleotides in the gene determines the protein."
            ),
            explanation=(
                "Scoring guide (3 points): (1) the template strand is transcribed into a complementary mRNA by base "
                "pairing; (2) the mRNA is read in groups of three (codons) and each codon specifies an amino acid "
                "according to the table; (3) the order of amino acids is the protein's sequence, so the DNA sequence "
                "determines the protein."
            ),
        )

    def _q_gene_activity_by_cell(self, params: dict[str, Any], rng: Rng) -> DraftQuestion:
        rows = params["activity"]
        actual = {r["gene"]: activity_category(r) for r in rows}
        key_gene = rng.choice([r["gene"] for r in rows])
        choices = []
        for r in rows:
            gene = r["gene"]
            if gene == key_gene:
                text = f"{gene} is {CATEGORY_TEXT[actual[gene]]}."
                choices.append(
                    DraftChoice(text, True, f"Correct: the table shows {gene} is {CATEGORY_TEXT[actual[gene]]}.")
                )
            else:
                wrong = rng.choice([c for c in CATEGORY_TEXT if c != actual[gene]])
                choices.append(
                    DraftChoice(
                        f"{gene} is {CATEGORY_TEXT[wrong]}.",
                        False,
                        f"The table shows {gene} is {CATEGORY_TEXT[actual[gene]]}, but this statement says it is {CATEGORY_TEXT[wrong]}.",
                    )
                )
        correct = next(c.text for c in choices if c.correct)
        return DraftQuestion(
            stem=(
                "The table shows which genes are active in two cell types, P and Q, from the same organism. Which "
                "statement is supported by the table?"
            ),
            answer=correct,
            explanation=(
                "Both cell types contain all four genes because they share the same DNA. They differ in which genes "
                f"are active, so they can make different proteins. {correct}"
            ),
            choices=choices,
        )
