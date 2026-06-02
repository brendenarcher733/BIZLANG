"""
Schema validator — reads only the CSV header row (zero data rows) and checks
that every column referenced in the pipeline actually exists.

Tracks schema evolution through SELECT and GROUP BY + aggregate steps so that
downstream column references are validated against the correct reduced schema.
"""

import pandas as pd

from ast_nodes import (
    LoadNode, FilterNode, SelectNode, GroupByNode, AggregateNode,
    HavingNode, SortNode, ChartNode, PipelineNode,
)


class ValidationError(Exception):
    def __init__(self, message: str, pos: int = -1):
        super().__init__(message)
        self.pos = pos


class SchemaValidator:
    """
    Validates all column references in a BizLang pipeline against the actual
    CSV schema before any data is loaded.  Raises ValidationError on the first
    problem found, with the set of available columns in the message.
    """

    def __init__(self):
        self._schema: list[str] = []
        self._pending_group: str | None = None

    def validate(self, pipeline: PipelineNode) -> None:
        load = pipeline.steps[0]
        assert isinstance(load, LoadNode)

        try:
            headers = pd.read_csv(load.filename, nrows=0)
            self._schema = list(headers.columns)
        except FileNotFoundError:
            raise ValidationError(f"File not found: '{load.filename}'")
        except Exception as exc:
            raise ValidationError(f"Cannot read '{load.filename}': {exc}")

        for node in pipeline.steps[1:]:
            self._check(node)

    # ── Per-node checks ───────────────────────────────────────────────────────

    def _check(self, node) -> None:
        if isinstance(node, (FilterNode, HavingNode)):
            for cond in node.conditions:
                self._require(cond.column)

        elif isinstance(node, SelectNode):
            for col in node.columns:
                self._require(col)
            self._schema = list(node.columns)          # schema narrows

        elif isinstance(node, GroupByNode):
            self._require(node.column)
            self._pending_group = node.column

        elif isinstance(node, AggregateNode):
            self._require(node.column)
            if self._pending_group:
                # After group + agg the only columns are the group key and the
                # aggregated column.
                self._schema = [self._pending_group, node.column]
                self._pending_group = None

        elif isinstance(node, SortNode):
            self._require(node.column)

        elif isinstance(node, ChartNode):
            self._require(node.x_column)
            self._require(node.y_column)

        # DisplayNode and ExportNode need no column validation

    def _require(self, col: str) -> None:
        if col not in self._schema:
            available = ", ".join(self._schema) if self._schema else "(none)"
            raise ValidationError(
                f"Column '{col}' not found.\n"
                f"  Available: {available}"
            )
