import pytest
from parser import parse, ParseError
from ast_nodes import (
    LoadNode, FilterNode, SelectNode, GroupByNode, AggregateNode,
    HavingNode, SortNode, DisplayNode, ExportNode, ChartNode,
)


# ── LOAD ──────────────────────────────────────────────────────────────────────

def test_parse_load_filename():
    p = parse("load sales.csv")
    assert isinstance(p.steps[0], LoadNode)
    assert p.steps[0].filename == "sales.csv"


def test_parse_load_nested_path():
    p = parse("load sample_data/sales.csv")
    assert p.steps[0].filename == "sample_data/sales.csv"


def test_parse_load_non_csv_raises():
    with pytest.raises(ParseError, match=".csv"):
        parse("load data.xlsx")


# ── FILTER ────────────────────────────────────────────────────────────────────

def test_parse_filter_single_condition():
    p = parse("load x.csv | filter region = South")
    f = p.steps[1]
    assert isinstance(f, FilterNode)
    assert len(f.conditions) == 1
    c = f.conditions[0]
    assert c.column == "region"
    assert c.operator == "="
    assert c.value == "South"


def test_parse_filter_all_operators():
    for op in ("=", "!=", ">", "<", ">=", "<="):
        p = parse(f"load x.csv | filter revenue {op} 100")
        assert p.steps[1].conditions[0].operator == op


def test_parse_filter_multi_and():
    p = parse("load x.csv | filter region = South AND revenue > 100")
    f = p.steps[1]
    assert f.logic == "AND"
    assert len(f.conditions) == 2
    assert f.conditions[1].column == "revenue"


def test_parse_filter_multi_or():
    p = parse("load x.csv | filter region = South OR region = North")
    f = p.steps[1]
    assert f.logic == "OR"
    assert len(f.conditions) == 2


def test_parse_filter_three_conditions():
    p = parse("load x.csv | filter a = 1 AND b = 2 AND c = 3")
    assert len(p.steps[1].conditions) == 3


# ── GROUP BY + AGGREGATE ──────────────────────────────────────────────────────

def test_parse_group_by_column():
    p = parse("load x.csv | group by month | sum revenue")
    g = p.steps[1]
    assert isinstance(g, GroupByNode)
    assert g.column == "month"


def test_parse_all_aggregate_functions():
    for func in ("sum", "avg", "count"):
        p = parse(f"load x.csv | group by col | {func} revenue")
        agg = p.steps[2]
        assert isinstance(agg, AggregateNode)
        assert agg.function == func
        assert agg.column == "revenue"


# ── SORT ──────────────────────────────────────────────────────────────────────

def test_parse_sort_default_asc():
    p = parse("load x.csv | sort revenue")
    s = p.steps[1]
    assert isinstance(s, SortNode)
    assert s.column == "revenue"
    assert s.order == "asc"


def test_parse_sort_desc():
    p = parse("load x.csv | sort revenue desc")
    assert p.steps[1].order == "desc"


def test_parse_sort_explicit_asc():
    p = parse("load x.csv | sort revenue asc")
    assert p.steps[1].order == "asc"


# ── DISPLAY ───────────────────────────────────────────────────────────────────

def test_parse_display_no_limit():
    p = parse("load x.csv | display")
    d = p.steps[1]
    assert isinstance(d, DisplayNode)
    assert d.limit is None


def test_parse_display_with_limit():
    p = parse("load x.csv | display 10")
    assert p.steps[1].limit == 10


# ── EXPORT ────────────────────────────────────────────────────────────────────

def test_parse_export_csv():
    p = parse("load x.csv | export results.csv")
    e = p.steps[1]
    assert isinstance(e, ExportNode)
    assert e.filename == "results.csv"
    assert e.fmt == "csv"


def test_parse_export_json():
    p = parse("load x.csv | export results.json")
    e = p.steps[1]
    assert e.fmt == "json"


# ── CHART ─────────────────────────────────────────────────────────────────────

def test_parse_chart_bar():
    p = parse("load x.csv | chart bar month revenue")
    c = p.steps[1]
    assert isinstance(c, ChartNode)
    assert c.chart_type == "bar"
    assert c.x_column == "month"
    assert c.y_column == "revenue"


def test_parse_all_chart_types():
    for ctype in ("bar", "line", "pie"):
        p = parse(f"load x.csv | chart {ctype} x y")
        assert p.steps[1].chart_type == ctype


def test_parse_unknown_chart_type_raises():
    with pytest.raises(ParseError, match="unsupported"):
        parse("load x.csv | chart scatter x y")


# ── Pipeline structure ────────────────────────────────────────────────────────

def test_pipeline_step_count():
    p = parse("load x.csv | filter r = S | group by m | sum v | sort v desc | chart bar m v")
    assert len(p.steps) == 6


def test_pipeline_preserves_order():
    p = parse("load x.csv | filter a = 1 | sort b | display")
    types = [type(s).__name__ for s in p.steps]
    assert types == ["LoadNode", "FilterNode", "SortNode", "DisplayNode"]


# ── Semantic validation ───────────────────────────────────────────────────────

def test_error_load_not_first():
    with pytest.raises(ParseError, match="must begin with"):
        parse("filter region = South | load x.csv")


def test_error_chart_not_last():
    with pytest.raises(ParseError, match="last command"):
        parse("load x.csv | chart bar x y | sort revenue")


def test_error_group_after_aggregate():
    with pytest.raises(ParseError, match="before"):
        parse("load x.csv | sum revenue | group by month")


def test_error_unknown_command():
    with pytest.raises(ParseError, match="unknown command"):
        parse("load x.csv | join other.csv")


def test_error_filter_missing_operator():
    with pytest.raises(ParseError):
        parse("load x.csv | filter region South")


def test_error_empty_pipeline():
    with pytest.raises(ParseError):
        parse("")


# ── SELECT ────────────────────────────────────────────────────────────────────

def test_parse_select_single_column():
    p = parse("load x.csv | select revenue")
    s = p.steps[1]
    assert isinstance(s, SelectNode)
    assert s.columns == ["revenue"]


def test_parse_select_multiple_columns():
    p = parse("load x.csv | select month, revenue, units")
    assert p.steps[1].columns == ["month", "revenue", "units"]


def test_parse_select_preserves_order():
    p = parse("load x.csv | select c, a, b")
    assert p.steps[1].columns == ["c", "a", "b"]


def test_parse_select_missing_columns_raises():
    with pytest.raises(ParseError):
        parse("load x.csv | select")


# ── HAVING ────────────────────────────────────────────────────────────────────

def test_parse_having_single_condition():
    p = parse("load x.csv | group by region | sum revenue | having revenue > 500")
    h = p.steps[3]
    assert isinstance(h, HavingNode)
    assert h.conditions[0].column == "revenue"
    assert h.conditions[0].operator == ">"
    assert h.conditions[0].value == "500"


def test_parse_having_multi_and():
    p = parse("load x.csv | group by region | sum revenue | having revenue > 100 AND revenue < 600")
    h = p.steps[3]
    assert h.logic == "AND"
    assert len(h.conditions) == 2


def test_parse_having_or():
    p = parse("load x.csv | group by region | sum revenue | having revenue < 100 OR revenue > 500")
    assert p.steps[3].logic == "OR"


def test_error_having_before_aggregation():
    with pytest.raises(ParseError, match="having"):
        parse("load x.csv | having revenue > 500")
