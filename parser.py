from lexer import tokenize, Token, TokenType, LexError
from ast_nodes import (
    Condition, LoadNode, FilterNode, GroupByNode, AggregateNode,
    SortNode, DisplayNode, ExportNode, ChartNode, PipelineNode,
)


class ParseError(Exception):
    pass


# Token types that are valid in column-name / value positions.
# Excludes AND, OR (logic connectors) and structural tokens.
_WORD_TYPES = {
    TokenType.IDENTIFIER, TokenType.NUMBER,
    TokenType.LOAD, TokenType.FILTER, TokenType.GROUP, TokenType.BY,
    TokenType.SUM, TokenType.AVG, TokenType.COUNT,
    TokenType.SORT, TokenType.DISPLAY, TokenType.EXPORT, TokenType.CHART,
    TokenType.ASC, TokenType.DESC,
}

_OPERATOR_TYPES = {
    TokenType.EQ, TokenType.NEQ,
    TokenType.GT, TokenType.LT,
    TokenType.GTE, TokenType.LTE,
}

_AGGREGATE_KEYWORDS = {TokenType.SUM, TokenType.AVG, TokenType.COUNT}
_CHART_TYPES        = {"bar", "line", "pie"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_on_pipe(tokens: list[Token]) -> list[list[Token]]:
    """Partition a flat token list into command segments on PIPE boundaries."""
    segments: list[list[Token]] = []
    current:  list[Token]       = []
    for tok in tokens:
        if tok.type is TokenType.EOF:
            break
        if tok.type is TokenType.PIPE:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def _word(tok: Token, context: str) -> str:
    """Assert token is usable as an identifier and return its value."""
    if tok.type not in _WORD_TYPES:
        raise ParseError(f"{context}: expected a name or value, got '{tok.value}'")
    return tok.value


# ── Command parsers ───────────────────────────────────────────────────────────

def _parse_load(toks: list[Token], step: int) -> LoadNode:
    if len(toks) != 2:
        raise ParseError(
            f"Step {step} · load: expected exactly one filename.\n"
            f"  Example: load sales.csv"
        )
    filename = toks[1].value
    if not filename.endswith(".csv"):
        raise ParseError(
            f"Step {step} · load: only .csv files are supported. Got '{filename}'"
        )
    return LoadNode(filename=filename)


def _parse_filter(toks: list[Token], step: int) -> FilterNode:
    """
    Grammar:  filter <col> <op> <val> [ (AND|OR) <col> <op> <val> … ]
    All conditions must share the same logic connector.
    """
    ctx = f"Step {step} · filter"
    conditions: list[Condition] = []
    logic = "AND"
    i = 1  # skip FILTER keyword

    while i < len(toks):
        if len(toks) - i < 3:
            raise ParseError(
                f"{ctx}: incomplete condition starting at token {i+1}.\n"
                f"  Expected: <column> <operator> <value>"
            )
        col_tok = toks[i]
        op_tok  = toks[i + 1]
        val_tok = toks[i + 2]

        if col_tok.type not in _WORD_TYPES:
            raise ParseError(f"{ctx}: expected a column name, got '{col_tok.value}'")
        if op_tok.type not in _OPERATOR_TYPES:
            raise ParseError(
                f"{ctx}: expected an operator (=, !=, >, <, >=, <=), got '{op_tok.value}'"
            )
        if val_tok.type not in _WORD_TYPES:
            raise ParseError(f"{ctx}: expected a value, got '{val_tok.value}'")

        conditions.append(Condition(col_tok.value, op_tok.value, val_tok.value))
        i += 3

        if i < len(toks):
            if toks[i].type is TokenType.AND:
                logic = "AND"
                i += 1
            elif toks[i].type is TokenType.OR:
                logic = "OR"
                i += 1
            else:
                raise ParseError(
                    f"{ctx}: expected 'AND' or 'OR' between conditions, got '{toks[i].value}'"
                )

    if not conditions:
        raise ParseError(f"{ctx}: at least one condition is required.\n  Example: filter region = West")

    return FilterNode(conditions=conditions, logic=logic)


def _parse_group_by(toks: list[Token], step: int) -> GroupByNode:
    if len(toks) < 3 or toks[1].type is not TokenType.BY:
        raise ParseError(
            f"Step {step} · group by: syntax error.\n"
            f"  Expected: group by <column>"
        )
    return GroupByNode(column=_word(toks[2], f"Step {step} · group by"))


def _parse_aggregate(toks: list[Token], step: int) -> AggregateNode:
    func = toks[0].value.lower()
    if len(toks) != 2:
        raise ParseError(
            f"Step {step} · {func}: expected exactly one column name.\n"
            f"  Example: {func} revenue"
        )
    return AggregateNode(function=func, column=_word(toks[1], f"Step {step} · {func}"))


def _parse_sort(toks: list[Token], step: int) -> SortNode:
    if len(toks) < 2:
        raise ParseError(
            f"Step {step} · sort: expected a column name.\n"
            f"  Example: sort revenue desc"
        )
    column = _word(toks[1], f"Step {step} · sort")
    order  = "asc"
    if len(toks) >= 3:
        if toks[2].type is TokenType.DESC:
            order = "desc"
        elif toks[2].type is TokenType.ASC:
            order = "asc"
        else:
            raise ParseError(
                f"Step {step} · sort: order must be 'asc' or 'desc', got '{toks[2].value}'"
            )
    return SortNode(column=column, order=order)


def _parse_display(toks: list[Token], step: int) -> DisplayNode:
    if len(toks) == 1:
        return DisplayNode(limit=None)
    if len(toks) == 2:
        if toks[1].type is not TokenType.NUMBER:
            raise ParseError(f"Step {step} · display: row limit must be a number.")
        return DisplayNode(limit=int(float(toks[1].value)))
    raise ParseError(
        f"Step {step} · display: too many arguments.\n"
        f"  Example: display   or   display 10"
    )


def _parse_export(toks: list[Token], step: int) -> ExportNode:
    if len(toks) != 2:
        raise ParseError(
            f"Step {step} · export: expected a filename.\n"
            f"  Example: export results.csv"
        )
    filename = toks[1].value
    fmt = "json" if filename.endswith(".json") else "csv"
    return ExportNode(filename=filename, fmt=fmt)


def _parse_chart(toks: list[Token], step: int) -> ChartNode:
    if len(toks) != 4:
        raise ParseError(
            f"Step {step} · chart: expected: chart <type> <x_column> <y_column>.\n"
            f"  Example: chart bar month revenue"
        )
    chart_type = toks[1].value.lower()
    if chart_type not in _CHART_TYPES:
        raise ParseError(
            f"Step {step} · chart: unsupported type '{chart_type}'.\n"
            f"  Supported: {', '.join(sorted(_CHART_TYPES))}"
        )
    return ChartNode(
        chart_type=chart_type,
        x_column=_word(toks[2], f"Step {step} · chart x"),
        y_column=_word(toks[3], f"Step {step} · chart y"),
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _parse_segment(toks: list[Token], step: int) -> object:
    if not toks:
        raise ParseError(f"Step {step}: empty command.")

    kw = toks[0].type

    if kw is TokenType.LOAD:
        return _parse_load(toks, step)
    elif kw is TokenType.FILTER:
        return _parse_filter(toks, step)
    elif kw is TokenType.GROUP:
        return _parse_group_by(toks, step)
    elif kw in _AGGREGATE_KEYWORDS:
        return _parse_aggregate(toks, step)
    elif kw is TokenType.SORT:
        return _parse_sort(toks, step)
    elif kw is TokenType.DISPLAY:
        return _parse_display(toks, step)
    elif kw is TokenType.EXPORT:
        return _parse_export(toks, step)
    elif kw is TokenType.CHART:
        return _parse_chart(toks, step)
    else:
        raise ParseError(
            f"Step {step}: unknown command '{toks[0].value}'.\n"
            f"  Supported: load  filter  group by  sum  avg  count  "
            f"sort  display  export  chart"
        )


# ── Semantic validation ───────────────────────────────────────────────────────

def validate(pipeline: PipelineNode) -> None:
    """Raise ParseError if the pipeline violates semantic rules."""
    steps = pipeline.steps
    if not steps:
        raise ParseError("Pipeline is empty.")

    if not isinstance(steps[0], LoadNode):
        raise ParseError(
            f"Every pipeline must begin with 'load'.\n"
            f"  Got: {type(steps[0]).__name__}"
        )

    # CHART must be the last step (if present anywhere)
    for step in steps[:-1]:
        if isinstance(step, ChartNode):
            raise ParseError("'chart' must be the last command in the pipeline.")

    # GROUP BY must precede any aggregation
    seen_agg = False
    for step in steps:
        if isinstance(step, AggregateNode):
            seen_agg = True
        if isinstance(step, GroupByNode) and seen_agg:
            raise ParseError("'group by' must come before 'sum', 'avg', or 'count'.")


# ── Public entry point ────────────────────────────────────────────────────────

def parse(source: str) -> PipelineNode:
    """
    Tokenize and parse a BizLang pipeline string.

    Returns a PipelineNode, or raises ParseError / LexError on invalid input.
    """
    try:
        tokens = tokenize(source)
    except LexError as e:
        raise ParseError(f"Tokenization failed: {e}") from e

    segments = _split_on_pipe(tokens)
    if not segments:
        raise ParseError("Input is empty — nothing to parse.")

    steps = [_parse_segment(seg, i + 1) for i, seg in enumerate(segments)]
    pipeline = PipelineNode(steps=steps)
    validate(pipeline)
    return pipeline
