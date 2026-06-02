from dataclasses import dataclass
from ast_nodes import (
    LoadNode, FilterNode, SelectNode, GroupByNode, AggregateNode,
    HavingNode, SortNode, DisplayNode, ExportNode, ChartNode, PipelineNode,
)


@dataclass
class PlanStep:
    number:      int
    operation:   str    # short tag, e.g. "LOAD"
    description: str    # human-readable action sentence


def plan(pipeline: PipelineNode) -> list[PlanStep]:
    """
    Derive a human-readable execution plan from the AST without running anything.
    Each PlanStep explains what will happen, not what did happen.
    """
    steps: list[PlanStep] = []

    for i, node in enumerate(pipeline.steps, 1):

        if isinstance(node, LoadNode):
            steps.append(PlanStep(i, "LOAD",
                f"Load '{node.filename}' into memory as a dataset"))

        elif isinstance(node, FilterNode):
            conds = f" {node.logic} ".join(
                f"{c.column} {c.operator} {c.value}" for c in node.conditions
            )
            steps.append(PlanStep(i, "FILTER",
                f"Keep only rows where {conds}"))

        elif isinstance(node, SelectNode):
            steps.append(PlanStep(i, "SELECT",
                f"Project to columns: {', '.join(node.columns)}"))

        elif isinstance(node, GroupByNode):
            steps.append(PlanStep(i, "GROUP BY",
                f"Group rows by the '{node.column}' column"))

        elif isinstance(node, AggregateNode):
            label = {"sum": "Sum", "avg": "Average", "count": "Count"}[node.function]
            steps.append(PlanStep(i, node.function.upper(),
                f"{label} the '{node.column}' column within each group"))

        elif isinstance(node, HavingNode):
            conds = f" {node.logic} ".join(
                f"{c.column} {c.operator} {c.value}" for c in node.conditions
            )
            steps.append(PlanStep(i, "HAVING",
                f"Keep only groups where {conds}"))

        elif isinstance(node, SortNode):
            direction = "highest to lowest" if node.order == "desc" else "lowest to highest"
            steps.append(PlanStep(i, "SORT",
                f"Sort results by '{node.column}' — {direction}"))

        elif isinstance(node, DisplayNode):
            limit_clause = f"top {node.limit} rows" if node.limit else "all rows"
            steps.append(PlanStep(i, "DISPLAY",
                f"Print the dataset ({limit_clause})"))

        elif isinstance(node, ExportNode):
            steps.append(PlanStep(i, "EXPORT",
                f"Save results to '{node.filename}' as {node.fmt.upper()}"))

        elif isinstance(node, ChartNode):
            axis = f"{node.x_column} × {node.y_column}"
            steps.append(PlanStep(i, "CHART",
                f"Render a {node.chart_type} chart — {axis}"))

    return steps
