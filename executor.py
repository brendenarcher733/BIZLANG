import time
from dataclasses import dataclass, field
from functools import reduce
from typing import Optional
import operator as _op

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ast_nodes import (
    LoadNode, FilterNode, GroupByNode, AggregateNode,
    SortNode, DisplayNode, ExportNode, ChartNode, PipelineNode,
)


_CHART_PALETTE = ["#4A90D9", "#5BA85B", "#E8643B", "#F5C518", "#8E44AD",
                  "#1ABC9C", "#E67E22", "#E74C3C", "#3498DB", "#9B59B6"]


@dataclass
class StepResult:
    operation:   str
    description: str
    rows_before: int
    rows_after:  int
    snapshot:    Optional[pd.DataFrame] = None   # set by DisplayNode


@dataclass
class ExecutionResult:
    steps:       list[StepResult]          = field(default_factory=list)
    df:          pd.DataFrame              = field(default_factory=pd.DataFrame)
    chart_path:  Optional[str]             = None
    exports:     list[str]                 = field(default_factory=list)
    scalars:     dict[str, float]          = field(default_factory=dict)
    elapsed_ms:  float                     = 0.0


class ExecutionError(Exception):
    pass


class Executor:
    """Walks a PipelineNode AST and executes each step directly via pandas."""

    def execute(self, pipeline: PipelineNode) -> ExecutionResult:
        result = ExecutionResult()
        df: pd.DataFrame = pd.DataFrame()
        _group_col: Optional[str] = None
        t0 = time.perf_counter()

        for node in pipeline.steps:
            rows_before = len(df)

            if isinstance(node, LoadNode):
                try:
                    df = pd.read_csv(node.filename)
                except FileNotFoundError:
                    raise ExecutionError(f"File not found: '{node.filename}'")
                except Exception as e:
                    raise ExecutionError(f"Failed to load '{node.filename}': {e}")
                result.steps.append(StepResult(
                    "LOAD",
                    f"Loaded {len(df):,} rows · {len(df.columns)} columns from '{node.filename}'",
                    0, len(df),
                ))

            elif isinstance(node, FilterNode):
                df = self._apply_filter(df, node)
                cond_str = f" {node.logic} ".join(
                    f"{c.column} {c.operator} {c.value}" for c in node.conditions
                )
                excluded = rows_before - len(df)
                result.steps.append(StepResult(
                    "FILTER",
                    f"{len(df):,} rows matched ({excluded:,} excluded) — {cond_str}",
                    rows_before, len(df),
                ))

            elif isinstance(node, GroupByNode):
                if node.column not in df.columns:
                    raise ExecutionError(
                        f"Column '{node.column}' not found. "
                        f"Available: {', '.join(df.columns)}"
                    )
                _group_col = node.column
                unique_vals = df[node.column].nunique()
                result.steps.append(StepResult(
                    "GROUP BY",
                    f"Grouped by '{node.column}' — {unique_vals} unique values",
                    rows_before, rows_before,
                ))

            elif isinstance(node, AggregateNode):
                func_map = {"sum": "sum", "avg": "mean", "count": "count"}
                pandas_func = func_map[node.function]

                if _group_col:
                    df = (
                        df.groupby(_group_col)[node.column]
                        .agg(pandas_func)
                        .reset_index()
                    )
                    _group_col = None
                    result.steps.append(StepResult(
                        node.function.upper(),
                        f"Computed {node.function}({node.column}) per group → {len(df)} groups",
                        rows_before, len(df),
                    ))
                else:
                    scalar = df[node.column].agg(pandas_func)
                    label = f"{node.function}({node.column})"
                    result.scalars[label] = float(scalar)
                    result.steps.append(StepResult(
                        node.function.upper(),
                        f"{label} = {scalar:,.4g}",
                        rows_before, rows_before,
                    ))

            elif isinstance(node, SortNode):
                if node.column not in df.columns:
                    raise ExecutionError(
                        f"Sort column '{node.column}' not found. "
                        f"Available: {', '.join(df.columns)}"
                    )
                ascending = node.order == "asc"
                df = df.sort_values(node.column, ascending=ascending).reset_index(drop=True)
                direction = "ascending" if ascending else "descending"
                result.steps.append(StepResult(
                    "SORT",
                    f"Sorted by '{node.column}' ({direction})",
                    rows_before, len(df),
                ))

            elif isinstance(node, DisplayNode):
                snapshot = df.head(node.limit).copy() if node.limit else df.copy()
                label = f"top {node.limit}" if node.limit else "all"
                result.steps.append(StepResult(
                    "DISPLAY",
                    f"Displaying {label} rows ({len(snapshot)} shown)",
                    rows_before, len(df),
                    snapshot=snapshot,
                ))

            elif isinstance(node, ExportNode):
                try:
                    if node.fmt == "json":
                        df.to_json(node.filename, orient="records", indent=2)
                    else:
                        df.to_csv(node.filename, index=False)
                except Exception as e:
                    raise ExecutionError(f"Export failed: {e}")
                result.exports.append(node.filename)
                result.steps.append(StepResult(
                    "EXPORT",
                    f"Exported {len(df):,} rows to '{node.filename}' ({node.fmt.upper()})",
                    rows_before, len(df),
                ))

            elif isinstance(node, ChartNode):
                path = self._render_chart(df, node)
                result.chart_path = path
                result.steps.append(StepResult(
                    "CHART",
                    f"Rendered {node.chart_type} chart → {path}",
                    rows_before, len(df),
                ))

        result.df = df
        result.elapsed_ms = (time.perf_counter() - t0) * 1000
        return result

    # ── Internals ─────────────────────────────────────────────────────────────

    def _apply_filter(self, df: pd.DataFrame, node: FilterNode) -> pd.DataFrame:
        def _mask(cond):
            col = cond.column
            if col not in df.columns:
                raise ExecutionError(
                    f"Filter column '{col}' not found. "
                    f"Available: {', '.join(df.columns)}"
                )
            try:
                val: float | str = float(cond.value)
            except ValueError:
                val = cond.value

            match cond.operator:
                case "=":  return df[col] == val
                case "!=": return df[col] != val
                case ">":  return df[col] >  val
                case "<":  return df[col] <  val
                case ">=": return df[col] >= val
                case "<=": return df[col] <= val
                case _:    raise ExecutionError(f"Unknown operator '{cond.operator}'")

        masks = [_mask(c) for c in node.conditions]
        combiner = _op.and_ if node.logic == "AND" else _op.or_
        return df[reduce(combiner, masks)]

    def _render_chart(self, df: pd.DataFrame, node: ChartNode) -> str:
        for col in (node.x_column, node.y_column):
            if col not in df.columns:
                raise ExecutionError(
                    f"Chart column '{col}' not found. "
                    f"Available: {', '.join(df.columns)}"
                )

        fig, ax = plt.subplots(figsize=(10, 5))
        x = df[node.x_column]
        y = df[node.y_column]
        xtitle = node.x_column.replace("_", " ").title()
        ytitle = node.y_column.replace("_", " ").title()

        if node.chart_type == "bar":
            colors = [_CHART_PALETTE[i % len(_CHART_PALETTE)] for i in range(len(x))]
            ax.bar(x, y, color=colors, edgecolor="white", linewidth=0.8)
            ax.set_xlabel(xtitle, fontsize=11)
            ax.set_ylabel(ytitle, fontsize=11)
            ax.set_title(f"{ytitle} by {xtitle}", fontsize=14, fontweight="bold", pad=14)
            ax.spines[["top", "right"]].set_visible(False)

        elif node.chart_type == "line":
            ax.plot(x, y, marker="o", color=_CHART_PALETTE[0],
                    linewidth=2.2, markersize=7, markerfacecolor="white",
                    markeredgewidth=2)
            ax.fill_between(range(len(x)), y, alpha=0.08, color=_CHART_PALETTE[0])
            ax.set_xticks(range(len(x)))
            ax.set_xticklabels(x)
            ax.set_xlabel(xtitle, fontsize=11)
            ax.set_ylabel(ytitle, fontsize=11)
            ax.set_title(f"{ytitle} over {xtitle}", fontsize=14, fontweight="bold", pad=14)
            ax.spines[["top", "right"]].set_visible(False)

        elif node.chart_type == "pie":
            colors = [_CHART_PALETTE[i % len(_CHART_PALETTE)] for i in range(len(x))]
            wedges, texts, autotexts = ax.pie(
                y, labels=x, autopct="%1.1f%%",
                colors=colors, startangle=140,
                wedgeprops={"edgecolor": "white", "linewidth": 1.5},
            )
            for t in autotexts:
                t.set_fontsize(9)
            ax.set_title(f"{ytitle} by {xtitle}", fontsize=14, fontweight="bold", pad=14)

        fig.patch.set_facecolor("#FAFAFA")
        ax.set_facecolor("#FAFAFA")
        plt.tight_layout()

        path = "chart_output.png"
        plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#FAFAFA")
        plt.close(fig)
        return path
