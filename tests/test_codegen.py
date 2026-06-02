import ast as py_ast
import pytest
from parser import parse
from codegen import CodeGenerator


@pytest.fixture
def gen():
    return CodeGenerator()


def _code(source: str) -> str:
    return CodeGenerator().generate(parse(source))


# ── Validity ──────────────────────────────────────────────────────────────────

def test_generated_code_is_valid_python():
    code = _code("load x.csv | filter region = South | group by month | sum revenue")
    py_ast.parse(code)   # raises SyntaxError on invalid Python


def test_all_demos_produce_valid_python():
    demos = [
        "load x.csv | filter region = South | group by month | sum revenue | chart bar month revenue",
        "load x.csv | group by region | avg revenue | sort revenue desc | chart pie region revenue",
        "load x.csv | filter revenue > 100 | group by month | sum revenue | chart line month revenue",
    ]
    for src in demos:
        py_ast.parse(_code(src))


# ── LOAD codegen ──────────────────────────────────────────────────────────────

def test_codegen_load_contains_read_csv():
    assert 'pd.read_csv("my_data.csv")' in _code("load my_data.csv")


# ── FILTER codegen ────────────────────────────────────────────────────────────

def test_codegen_filter_string_value_is_quoted():
    code = _code("load x.csv | filter region = South")
    assert '"South"' in code


def test_codegen_filter_numeric_value_is_unquoted():
    code = _code("load x.csv | filter revenue > 100")
    assert "100" in code
    assert '"100"' not in code


def test_codegen_filter_eq_maps_to_double_eq():
    code = _code("load x.csv | filter region = South")
    assert "==" in code


def test_codegen_multi_condition_and_uses_ampersand():
    code = _code("load x.csv | filter region = South AND revenue > 100")
    assert " & " in code


def test_codegen_multi_condition_or_uses_pipe():
    code = _code("load x.csv | filter region = South OR region = North")
    assert " | " in code


# ── SORT codegen ──────────────────────────────────────────────────────────────

def test_codegen_sort_desc_sets_ascending_false():
    assert "ascending=False" in _code("load x.csv | sort revenue desc")


def test_codegen_sort_asc_sets_ascending_true():
    assert "ascending=True" in _code("load x.csv | sort revenue asc")


# ── EXPORT codegen ────────────────────────────────────────────────────────────

def test_codegen_export_csv_uses_to_csv():
    assert "to_csv" in _code("load x.csv | export results.csv")


def test_codegen_export_json_uses_to_json():
    assert "to_json" in _code("load x.csv | export results.json")


# ── CHART codegen ─────────────────────────────────────────────────────────────

def test_codegen_bar_chart():
    assert "plt.bar" in _code("load x.csv | chart bar month revenue")


def test_codegen_line_chart():
    assert "plt.plot" in _code("load x.csv | chart line month revenue")


def test_codegen_pie_chart():
    assert "plt.pie" in _code("load x.csv | chart pie region revenue")


def test_codegen_chart_saves_file():
    code = _code("load x.csv | chart bar x y")
    assert "savefig" in code


# ── SELECT codegen ────────────────────────────────────────────────────────────

def test_codegen_select_single_column():
    code = _code("load x.csv | select revenue")
    assert '"revenue"' in code
    py_ast.parse(code)


def test_codegen_select_multiple_columns():
    code = _code("load x.csv | select month, revenue")
    assert '"month"' in code
    assert '"revenue"' in code
    py_ast.parse(code)


# ── HAVING codegen ────────────────────────────────────────────────────────────

def test_codegen_having_produces_valid_python():
    code = _code("load x.csv | group by region | sum revenue | having revenue > 500")
    py_ast.parse(code)


def test_codegen_having_uses_correct_comparison():
    code = _code("load x.csv | group by region | sum revenue | having revenue > 500")
    assert "> 500" in code or ">500" in code


def test_codegen_having_multi_condition_and():
    code = _code(
        "load x.csv | group by region | sum revenue | having revenue > 100 AND revenue < 600"
    )
    assert " & " in code
    py_ast.parse(code)
