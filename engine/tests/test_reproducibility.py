"""TEST_SUITE_SPEC §13 Reproduksibilitas & presisi."""

import ast
import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from pricing_engine.core import ENGINE_VERSION, quantize_money
from pricing_engine.pricing import PercentageFee, PricingMethod, calculate_price

SRC = Path(__file__).resolve().parents[1] / "src" / "pricing_engine"

INPUT = dict(
    method=PricingMethod.TARGET_CONTRIBUTION_MARGIN,
    unit_cost="60000",
    target_margin="0.30",
    discount="0.20",
    fees=[PercentageFee("marketplace", "0.10")],
)


def test_REP_01_identical_output():
    a = calculate_price(**INPUT)
    b = calculate_price(**INPUT)
    assert a == b
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(b.to_dict(), sort_keys=True)
    assert a.engine_version == ENGINE_VERSION
    assert len(a.input_hash) == 64


def test_REP_02_hash_independent_of_key_order_and_notation():
    reordered = dict(reversed(list(INPUT.items())))
    reordered["unit_cost"] = D("60000.00")  # notasi berbeda, nilai sama
    assert calculate_price(**reordered).input_hash == calculate_price(**INPUT).input_hash


def test_REP_02b_hash_changes_with_value():
    assert calculate_price(**{**INPUT, "unit_cost": "60001"}).input_hash != calculate_price(**INPUT).input_hash


FORBIDDEN_CALLS = {("datetime", "now"), ("datetime", "today"), ("date", "today"), ("time", "time"), ("random", "random")}


@pytest.mark.parametrize("path", sorted(SRC.glob("*.py")), ids=lambda p: p.name)
def test_REP_03_and_PRE_01_static_purity(path):
    """Engine tidak membaca jam sistem / acak dan tidak memakai float di jalur kalkulasi."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            assert not isinstance(node.value, float), f"{path.name}:{node.lineno} literal float"
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id != "float", f"{path.name}:{node.lineno} float()"
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                assert (node.func.value.id, node.func.attr) not in FORBIDDEN_CALLS, f"{path.name}:{node.lineno}"
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            assert not any(n in {"random", "time", "requests", "socket", "sqlalchemy"} for n in names), path.name


def test_PRE_01_decimal_exact():
    assert D("0.1") + D("0.2") == D("0.3")


def test_PRE_02_currency_precision():
    assert quantize_money(D("85714.2857"), "IDR") == D("85714")
    assert quantize_money(D("85714.2857"), "USD") == D("85714.29")
    assert quantize_money(D("0.5"), "IDR") == D("1")  # ROUND_HALF_UP


@pytest.mark.skip(reason="HIS-02 diuji di fase backend: memerlukan tabel costing_versions berversi")
def test_HIS_02_history_not_deleted():
    pass
