import pytest
import pandas as pd

# 8-row dataset: 2 regions × 4 months — simple enough for exact assertions
_DATA = {
    "month":   ["Jan", "Jan", "Feb", "Feb", "Mar", "Mar", "Apr", "Apr"],
    "region":  ["South", "North", "South", "North", "South", "North", "South", "North"],
    "revenue": [100,     120,    90,      140,    150,     160,    200,     180],
    "units":   [10,      14,     8,       16,     18,      19,     24,      21],
}

# Derived constants tests can import for clarity
TOTAL_ROWS    = 8
SOUTH_ROWS    = 4
SOUTH_REVENUE = 540   # 100+90+150+200
TOTAL_REVENUE = 1140  # sum of all revenue


@pytest.fixture
def csv_path(tmp_path, monkeypatch):
    """Write sample data to a temp CSV and cd there so relative paths work."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "sales.csv"
    pd.DataFrame(_DATA).to_csv(path, index=False)
    return "sales.csv"


@pytest.fixture
def sample_df():
    return pd.DataFrame(_DATA)
