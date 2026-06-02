import pytest
from parser import parse
from validator import SchemaValidator, ValidationError


@pytest.fixture
def v():
    return SchemaValidator()


# ── Happy paths ───────────────────────────────────────────────────────────────

def test_valid_pipeline_passes(v, csv_path):
    v.validate(parse(f"load {csv_path} | filter region = South | group by month | sum revenue"))


def test_valid_select_passes(v, csv_path):
    v.validate(parse(f"load {csv_path} | select month, revenue"))


def test_valid_having_passes(v, csv_path):
    v.validate(parse(
        f"load {csv_path} | group by region | sum revenue | having revenue > 100"
    ))


def test_valid_sort_passes(v, csv_path):
    v.validate(parse(f"load {csv_path} | sort revenue desc"))


def test_valid_chart_passes(v, csv_path):
    v.validate(parse(
        f"load {csv_path} | group by month | sum revenue | chart bar month revenue"
    ))


# ── Column not found ──────────────────────────────────────────────────────────

def test_filter_bad_column_raises(v, csv_path):
    with pytest.raises(ValidationError, match="'bogus'"):
        v.validate(parse(f"load {csv_path} | filter bogus = X"))


def test_group_by_bad_column_raises(v, csv_path):
    with pytest.raises(ValidationError, match="'nonexistent'"):
        v.validate(parse(f"load {csv_path} | group by nonexistent | sum revenue"))


def test_aggregate_bad_column_raises(v, csv_path):
    with pytest.raises(ValidationError, match="'nope'"):
        v.validate(parse(f"load {csv_path} | group by region | sum nope"))


def test_sort_bad_column_raises(v, csv_path):
    with pytest.raises(ValidationError, match="'missing'"):
        v.validate(parse(f"load {csv_path} | sort missing"))


def test_chart_bad_x_column_raises(v, csv_path):
    with pytest.raises(ValidationError, match="'badx'"):
        v.validate(parse(
            f"load {csv_path} | group by region | sum revenue | chart bar badx revenue"
        ))


def test_chart_bad_y_column_raises(v, csv_path):
    with pytest.raises(ValidationError, match="'bady'"):
        v.validate(parse(
            f"load {csv_path} | group by region | sum revenue | chart bar region bady"
        ))


def test_having_bad_column_raises(v, csv_path):
    with pytest.raises(ValidationError, match="'ghost'"):
        v.validate(parse(
            f"load {csv_path} | group by region | sum revenue | having ghost > 0"
        ))


# ── Schema evolution ──────────────────────────────────────────────────────────

def test_select_reduces_schema(v, csv_path):
    # 'units' dropped by select; sorting on it should fail
    with pytest.raises(ValidationError, match="'units'"):
        v.validate(parse(
            f"load {csv_path} | select month, revenue | sort units"
        ))


def test_group_agg_updates_schema(v, csv_path):
    # After group by month | sum revenue, only [month, revenue] remain
    with pytest.raises(ValidationError, match="'region'"):
        v.validate(parse(
            f"load {csv_path} | group by month | sum revenue | sort region"
        ))


def test_column_available_before_select_removed_after(v, csv_path):
    # Filtering on 'units' before select is fine; after select it's gone
    v.validate(parse(
        f"load {csv_path} | filter units > 10 | select month, revenue"
    ))


# ── File errors ───────────────────────────────────────────────────────────────

def test_file_not_found_raises(v):
    with pytest.raises(ValidationError, match="not found"):
        v.validate(parse("load ghost.csv"))


def test_error_message_lists_available_columns(v, csv_path):
    with pytest.raises(ValidationError) as exc_info:
        v.validate(parse(f"load {csv_path} | filter badcol = X"))
    assert "Available" in str(exc_info.value)
    assert "region" in str(exc_info.value)
