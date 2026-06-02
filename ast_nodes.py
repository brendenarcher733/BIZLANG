from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Condition:
    """A single predicate used inside a FilterNode."""
    column:   str
    operator: str
    value:    str

    def to_dict(self) -> dict:
        return {"column": self.column, "operator": self.operator, "value": self.value}

    def __repr__(self) -> str:
        return f"{self.column} {self.operator} {self.value}"


class LoadNode:
    def __init__(self, filename: str):
        self.filename = filename

    def to_dict(self) -> dict:
        return {"node": "LoadNode", "filename": self.filename}

    def __repr__(self) -> str:
        return f"LoadNode(filename='{self.filename}')"


class FilterNode:
    """One or more filter conditions joined by a single logic connector (AND / OR)."""
    def __init__(self, conditions: List[Condition], logic: str = "AND"):
        self.conditions = conditions
        self.logic = logic.upper()

    def to_dict(self) -> dict:
        return {
            "node":       "FilterNode",
            "logic":      self.logic,
            "conditions": [c.to_dict() for c in self.conditions],
        }

    def __repr__(self) -> str:
        parts = f" {self.logic} ".join(repr(c) for c in self.conditions)
        return f"FilterNode({parts})"


class GroupByNode:
    def __init__(self, column: str):
        self.column = column

    def to_dict(self) -> dict:
        return {"node": "GroupByNode", "column": self.column}

    def __repr__(self) -> str:
        return f"GroupByNode(column='{self.column}')"


class AggregateNode:
    def __init__(self, function: str, column: str):
        self.function = function   # "sum" | "avg" | "count"
        self.column   = column

    def to_dict(self) -> dict:
        return {"node": "AggregateNode", "function": self.function, "column": self.column}

    def __repr__(self) -> str:
        return f"AggregateNode(function='{self.function}', column='{self.column}')"


class SelectNode:
    """Project a subset of columns: select col1, col2, ..."""
    def __init__(self, columns: List[str]):
        self.columns = columns

    def to_dict(self) -> dict:
        return {"node": "SelectNode", "columns": self.columns}

    def __repr__(self) -> str:
        return f"SelectNode(columns={self.columns!r})"


class HavingNode:
    """Post-aggregation filter — identical syntax to FilterNode."""
    def __init__(self, conditions: List[Condition], logic: str = "AND"):
        self.conditions = conditions
        self.logic = logic.upper()

    def to_dict(self) -> dict:
        return {
            "node":       "HavingNode",
            "logic":      self.logic,
            "conditions": [c.to_dict() for c in self.conditions],
        }

    def __repr__(self) -> str:
        parts = f" {self.logic} ".join(repr(c) for c in self.conditions)
        return f"HavingNode({parts})"


class SortNode:
    def __init__(self, column: str, order: str = "asc"):
        self.column = column
        self.order  = order.lower()   # "asc" | "desc"

    def to_dict(self) -> dict:
        return {"node": "SortNode", "column": self.column, "order": self.order}

    def __repr__(self) -> str:
        return f"SortNode(column='{self.column}', order='{self.order}')"


class DisplayNode:
    def __init__(self, limit: Optional[int] = None):
        self.limit = limit   # None means all rows

    def to_dict(self) -> dict:
        return {"node": "DisplayNode", "limit": self.limit}

    def __repr__(self) -> str:
        return f"DisplayNode(limit={self.limit!r})"


class ExportNode:
    def __init__(self, filename: str, fmt: str = "csv"):
        self.filename = filename
        self.fmt      = fmt.lower()   # "csv" | "json"

    def to_dict(self) -> dict:
        return {"node": "ExportNode", "filename": self.filename, "format": self.fmt}

    def __repr__(self) -> str:
        return f"ExportNode(filename='{self.filename}', format='{self.fmt}')"


class ChartNode:
    def __init__(self, chart_type: str, x_column: str, y_column: str):
        self.chart_type = chart_type   # "bar" | "line" | "pie"
        self.x_column   = x_column
        self.y_column   = y_column

    def to_dict(self) -> dict:
        return {
            "node":       "ChartNode",
            "chart_type": self.chart_type,
            "x_column":   self.x_column,
            "y_column":   self.y_column,
        }

    def __repr__(self) -> str:
        return f"ChartNode(type='{self.chart_type}', x='{self.x_column}', y='{self.y_column}')"


class PipelineNode:
    """Root AST node — an ordered list of all pipeline steps."""
    def __init__(self, steps: list):
        self.steps = steps

    def to_dict(self) -> dict:
        return {
            "node":  "PipelineNode",
            "steps": [s.to_dict() for s in self.steps],
        }

    def __repr__(self) -> str:
        parts = "\n  ".join(repr(s) for s in self.steps)
        return f"PipelineNode(\n  {parts}\n)"
