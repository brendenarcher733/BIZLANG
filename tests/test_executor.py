import json
import pathlib

import pytest
import pandas as pd

from parser import parse
from executor import Executor, ExecutionError
from tests.conftest import SOUTH_ROWS, TOTAL_ROWS, SOUTH_REVENUE, TOTAL_REVENUE


@pytest.fixture
def ex():
    return Executor()


# ── LOAD ──────────────────────────────────────────────────────────────────────

def test_load_shape(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path}"))
    assert r.df.shape == (TOTAL_ROWS, 4)
    assert list(r.df.columns) == ["month", "region", "revenue", "units"]


def test_load_step_result(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path}"))
    step = r.steps[0]
    assert step.operation == "LOAD"
    assert step.rows_after == TOTAL_ROWS


def test_load_file_not_found_raises(ex):
    with pytest.raises(ExecutionError, match="not found"):
        ex.execute(parse("load nonexistent.csv"))


# ── FILTER ────────────────────────────────────────────────────────────────────

def test_filter_string_equality(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | filter region = South"))
    assert len(r.df) == SOUTH_ROWS
    assert (r.df["region"] == "South").all()


def test_filter_numeric_gt(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | filter revenue > 100"))
    assert (r.df["revenue"] > 100).all()


def test_filter_numeric_lte(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | filter revenue <= 100"))
    assert (r.df["revenue"] <= 100).all()


def test_filter_not_equal(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | filter region != South"))
    assert (r.df["region"] != "South").all()
    assert len(r.df) == TOTAL_ROWS - SOUTH_ROWS


def test_filter_multi_and(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | filter region = North AND revenue > 140"))
    assert (r.df["region"] == "North").all()
    assert (r.df["revenue"] > 140).all()
    assert len(r.df) == 2   # Mar North(160) and Apr North(180)


def test_filter_multi_or(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | filter region = South OR region = North"))
    assert len(r.df) == TOTAL_ROWS   # all rows match one or the other


def test_filter_step_tracks_row_counts(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | filter region = South"))
    step = r.steps[1]
    assert step.rows_before == TOTAL_ROWS
    assert step.rows_after  == SOUTH_ROWS


def test_filter_bad_column_raises(ex, csv_path):
    with pytest.raises(ExecutionError, match="not found"):
        ex.execute(parse(f"load {csv_path} | filter bogus = X"))


# ── GROUP BY + AGGREGATE ──────────────────────────────────────────────────────

def test_group_sum_correct_totals(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | group by region | sum revenue"))
    assert set(r.df["region"]) == {"South", "North"}
    south = r.df.loc[r.df["region"] == "South", "revenue"].iloc[0]
    assert south == SOUTH_REVENUE


def test_group_avg_produces_one_row_per_group(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | group by region | avg revenue"))
    assert len(r.df) == 2


def test_group_count(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | group by region | count units"))
    counts = set(r.df["units"])
    assert counts == {4}   # 4 months per region


def test_scalar_sum_no_group(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | sum revenue"))
    assert "sum(revenue)" in r.scalars
    assert r.scalars["sum(revenue)"] == pytest.approx(TOTAL_REVENUE)


def test_scalar_avg_no_group(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | avg revenue"))
    assert r.scalars["avg(revenue)"] == pytest.approx(TOTAL_REVENUE / TOTAL_ROWS)


# ── SORT ──────────────────────────────────────────────────────────────────────

def test_sort_asc_ordered(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | sort revenue asc"))
    vals = list(r.df["revenue"])
    assert vals == sorted(vals)


def test_sort_desc_ordered(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | sort revenue desc"))
    vals = list(r.df["revenue"])
    assert vals == sorted(vals, reverse=True)


def test_sort_bad_column_raises(ex, csv_path):
    with pytest.raises(ExecutionError, match="not found"):
        ex.execute(parse(f"load {csv_path} | sort nonexistent"))


# ── DISPLAY ───────────────────────────────────────────────────────────────────

def test_display_captures_all_rows(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | display"))
    snap = next(s for s in r.steps if s.operation == "DISPLAY")
    assert snap.snapshot is not None
    assert len(snap.snapshot) == TOTAL_ROWS


def test_display_respects_limit(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | display 3"))
    snap = next(s for s in r.steps if s.operation == "DISPLAY")
    assert len(snap.snapshot) == 3


def test_display_does_not_mutate_df(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path} | display 2"))
    assert len(r.df) == TOTAL_ROWS   # underlying df is unchanged


# ── EXPORT ────────────────────────────────────────────────────────────────────

def test_export_csv_writes_file(ex, csv_path, tmp_path):
    out = "exported.csv"
    r = ex.execute(parse(f"load {csv_path} | filter region = South | export {out}"))
    assert out in r.exports
    written = pd.read_csv(out)
    assert len(written) == SOUTH_ROWS
    assert list(written.columns) == ["month", "region", "revenue", "units"]


def test_export_json_writes_valid_json(ex, csv_path, tmp_path):
    out = "exported.json"
    ex.execute(parse(f"load {csv_path} | export {out}"))
    data = json.loads(pathlib.Path(out).read_text())
    assert isinstance(data, list)
    assert len(data) == TOTAL_ROWS


# ── TIMING ────────────────────────────────────────────────────────────────────

def test_elapsed_ms_is_positive(ex, csv_path):
    r = ex.execute(parse(f"load {csv_path}"))
    assert r.elapsed_ms > 0


# ── FULL PIPELINE ─────────────────────────────────────────────────────────────

def test_full_pipeline_produces_correct_groups(ex, csv_path):
    r = ex.execute(parse(
        f"load {csv_path} | filter region = South | group by month | sum revenue | sort revenue desc"
    ))
    assert list(r.df.columns) == ["month", "revenue"]
    assert len(r.df) == 4
    assert r.df["revenue"].iloc[0] == 200   # Apr should be first after desc sort
