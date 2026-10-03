"""DNA to protein (B-LS1-1): transcribe a template strand and translate the mRNA with a displayed codon table.

Curated data only: the standard genetic code. Every key is computed from the strands and table the student sees.
Scope follows the Biology 1 boundary: no initiation, elongation or termination steps, no named genes or proteins, and
no effects of sequence changes (those belong to B-LS3-2).
"""

from itertools import product
from typing import Any

from app.services.engine.core import GenerationError, Rng

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


def strand_text(seq: str, left: str, right: str) -> str:
    return f"{left}′-{seq}-{right}′"


def transcribe_candidates(gene: dict[str, Any]) -> list[tuple[str, str]]:
    """Wrong mRNA strings a student might choose, each distinct from the key and from each other."""
    key, template = gene["mrna"], gene["template"]
    raw = [
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
    return _distinct([gene["protein"], o["template_as_mrna"], o["reversed"], o["no_start"]])


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
