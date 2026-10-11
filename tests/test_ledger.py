from src.mcd_mcp.brain import NutritionFact
from src.nutrition.ledger import NutritionLedger


def _fact(name="巨无霸", kcal=550.0, protein=27.0):
    return NutritionFact(name=name, energy_kcal=kcal, protein_g=protein, fat_g=30.0,
                         carb_g=45.0, sodium_mg=1000.0, calcium_mg=200.0)


def test_add_and_summarize(tmp_path):
    ledger = NutritionLedger(tmp_path / "nutrition.json")
    ledger.add_fact(_fact(), date="2026-10-10")
    ledger.add_fact(_fact("薯条", kcal=320.0, protein=4.0), date="2026-10-10")

    totals = ledger.totals("2026-10-10")
    assert totals["items"] == 2
    assert totals["energy_kcal"] == 870.0
    assert totals["protein_g"] == 31.0
    assert "870" in ledger.summary("2026-10-10")


def test_other_days_are_not_counted(tmp_path):
    ledger = NutritionLedger(tmp_path / "nutrition.json")
    ledger.add_fact(_fact(), date="2026-10-10")
    assert ledger.totals("2026-10-11")["items"] == 0
    assert ledger.summary("2026-10-11") == "今天还没记账"


def test_persists_across_instances(tmp_path):
    path = tmp_path / "nutrition.json"
    NutritionLedger(path).add_fact(_fact(), date="2026-10-10")
    assert NutritionLedger(path).day("2026-10-10")[0].meal_name == "巨无霸"


def test_selected_meal_quantity_survive_reopen(tmp_path):
    fact = NutritionFact(name="巨无霸", energy_kcal=513, protein_g=27, sodium_mg=961, note="服务端说明")
    ledger = NutritionLedger(tmp_path / "nutrition.json")
    entry = ledger.add_fact(fact, quantity=2)
    assert entry.meal_name == "巨无霸"
    assert entry.quantity == 2
    assert entry.energy_kcal == 1026
    assert entry.note == fact.note
    reopened = NutritionLedger(ledger.path)
    assert reopened.entries[0] == entry
    assert reopened.totals()["sodium_mg"] == 1922


def test_quantity_default_one_and_invalid_never_writes(tmp_path):
    import pytest
    ledger = NutritionLedger(tmp_path / "nutrition.json")
    assert ledger.add_fact(NutritionFact(name="纯悦")).quantity == 1
    for quantity in (0, -1, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            ledger.add_fact(NutritionFact(name="纯悦"), quantity=quantity)
    assert len(ledger.entries) == 1
