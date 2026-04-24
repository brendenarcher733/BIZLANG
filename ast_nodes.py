# ast_nodes.py
# ─────────────────────────────────────────────────────────────────────────────
# AST Node definitions for BizLang.
#
# Each class represents one command in the pipeline.
# They are plain Python dataclasses — no magic, easy to inspect and print.
# ─────────────────────────────────────────────────────────────────────────────


class LoadNode:
    """
    Represents:  load <filename>
    Example:     load sales.csv
    """
    def __init__(self, filename: str):
        self.filename = filename          # e.g. "sales.csv"

    def to_dict(self) -> dict:
        return {"node": "LoadNode", "filename": self.filename}

    def __repr__(self) -> str:
        return f"LoadNode(filename='{self.filename}')"


class FilterNode:
    """
    Represents:  filter <column> = <value>
    Example:     filter region = South

    Supports operators: =  !=  >  <  >=  <=
    """
    def __init__(self, column: str, operator: str, value: str):
        self.column   = column            # e.g. "region"
        self.operator = operator          # e.g. "="
        self.value    = value             # e.g. "South"

    def to_dict(self) -> dict:
        return {
            "node":     "FilterNode",
            "column":   self.column,
            "operator": self.operator,
            "value":    self.value,
        }

    def __repr__(self) -> str:
        return f"FilterNode(column='{self.column}', operator='{self.operator}', value='{self.value}')"


class GroupByNode:
    """
    Represents:  group by <column>
    Example:     group by month
    """
    def __init__(self, column: str):
        self.column = column              # e.g. "month"

    def to_dict(self) -> dict:
        return {"node": "GroupByNode", "column": self.column}

    def __repr__(self) -> str:
        return f"GroupByNode(column='{self.column}')"


class AggregateNode:
    """
    Represents:  sum <column>  |  avg <column>  |  count <column>
    Example:     sum revenue

    The function field holds the aggregation type: "sum", "avg", or "count".
    """
    def __init__(self, function: str, column: str):
        self.function = function          # "sum" | "avg" | "count"
        self.column   = column            # e.g. "revenue"

    def to_dict(self) -> dict:
        return {
            "node":     "AggregateNode",
            "function": self.function,
            "column":   self.column,
        }

    def __repr__(self) -> str:
        return f"AggregateNode(function='{self.function}', column='{self.column}')"


class ChartNode:
    """
    Represents:  chart <type> <x_column> <y_column>
    Example:     chart bar month revenue

    Supported chart types: bar, line, pie
    """
    def __init__(self, chart_type: str, x_column: str, y_column: str):
        self.chart_type = chart_type      # "bar" | "line" | "pie"
        self.x_column   = x_column        # column for the x-axis
        self.y_column   = y_column        # column for the y-axis

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
    """
    The root AST node.
    Holds an ordered list of all parsed command nodes.
    The code generator walks this list top-to-bottom.
    """
    def __init__(self, steps: list):
        self.steps = steps                # list of Node objects in order

    def to_dict(self) -> dict:
        return {
            "node":  "PipelineNode",
            "steps": [step.to_dict() for step in self.steps],
        }

    def __repr__(self) -> str:
        steps_repr = "\n  ".join(repr(s) for s in self.steps)
        return f"PipelineNode(\n  {steps_repr}\n)"
