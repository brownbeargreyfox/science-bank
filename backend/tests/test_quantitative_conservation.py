"""Independent catalog and arithmetic checks for the C-PS1-7 family."""

from fractions import Fraction

import pytest

from app.services.engine.core import Rng
from app.services.families.quantitative_conservation import ATOMIC_MASS, REACTIONS, QuantitativeConservation, molar_mass


def _manual_side_atoms(species):
    """Intentionally independent from the family atom-total helper."""
    totals = {}
    for _formula, _name, coefficient, atoms in species:
        for element, count in atoms.items():
            totals[element] = totals.get(element, 0) + coefficient * count
    return totals


@pytest.mark.parametrize("reaction", sorted(REACTIONS))
def test_curated_catalog_conserves_atoms_and_mass(reaction):
    species = REACTIONS[reaction]["species"]
    reactants, products = species[:2], species[2:]
    assert _manual_side_atoms(reactants) == _manual_side_atoms(products)

    def mass(side):
        return sum(
            (coefficient * sum(ATOMIC_MASS[e] * n for e, n in atoms.items()) for _, _, coefficient, atoms in side),
            Fraction(),
        )

    assert mass(reactants) == mass(products)


@pytest.mark.parametrize("reaction", sorted(REACTIONS))
def test_catalog_formula_masses_and_coefficient_ratios(reaction):
    species = REACTIONS[reaction]["species"]
    for _formula, _name, coefficient, atoms in species:
        assert molar_mass(atoms) == sum((ATOMIC_MASS[e] * n for e, n in atoms.items()), Fraction())
        assert coefficient > 0
    assert Fraction(species[-1][2], species[0][2]) > 0


@pytest.mark.parametrize("reaction", sorted(REACTIONS))
def test_scenario_uses_explicit_dimensional_path_and_exact_preformat_math(reaction):
    family = QuantitativeConservation()
    scenario = next(
        family.build_scenario(Rng("catalog", attempt))
        for attempt in range(100)
        if family.build_scenario(Rng("catalog", attempt))["reaction"] == reaction
    )
    path = scenario["dimensional_analysis"]
    assert path == scenario["unit_path"].split(" → ")
    assert path[0].startswith("g ") and path[1].startswith("mol ")
    assert path[2].startswith("mol ") and path[3].startswith("g ")
    given = scenario["species"][scenario["given"]]
    assert Fraction(str(scenario["given_mass"])) / Fraction(str(given["molar_mass"])) == Fraction(
        str(scenario["given_moles"])
    )
