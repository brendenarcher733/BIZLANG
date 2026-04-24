# parser.py
# ─────────────────────────────────────────────────────────────────────────────
# BizLang Parser
#
# Strategy:
#   1. Split the full input string on "|" to get individual command strings.
#   2. Strip and lowercase each command to identify its type.
#   3. Dispatch to a dedicated parse function that validates the command
#      and returns the correct AST node.
#   4. Wrap all nodes in a PipelineNode and return it.
#
# No external libraries — just Python string operations.
# ─────────────────────────────────────────────────────────────────────────────

from ast_nodes import (
    LoadNode, FilterNode, GroupByNode,
    AggregateNode, ChartNode, PipelineNode,
)


# ── Supported filter operators (order matters — longer first to avoid partial match) ──
FILTER_OPERATORS = ["!=", ">=", "<=", "=", ">", "<"]

# ── Supported aggregation keywords ────────────────────────────────────────────
AGGREGATE_FUNCTIONS = ["sum", "avg", "count"]

# ── Supported chart types ──────────────────────────────────────────────────────
CHART_TYPES = ["bar", "line", "pie"]


class ParseError(Exception):
    """Raised when BizLang input does not match the grammar."""
    pass


# ── Individual command parsers ─────────────────────────────────────────────────

def parse_load(tokens: list[str]) -> LoadNode:
    """
    Grammar:  load <filename>
    Tokens:   ["load", "sales.csv"]
    """
    if len(tokens) != 2:
        raise ParseError(
            f"'load' expects exactly one argument (a filename).\n"
            f"  Got: {' '.join(tokens)}\n"
            f"  Expected: load <filename>"
        )
    filename = tokens[1]
    if not filename.endswith(".csv"):
        raise ParseError(
            f"'load' only supports .csv files. Got: '{filename}'"
        )
    return LoadNode(filename=filename)


def parse_filter(tokens: list[str]) -> FilterNode:
    """
    Grammar:  filter <column> <operator> <value>
    Tokens:   ["filter", "region", "=", "South"]

    We rejoin everything after "filter" and then scan for a known operator
    so that column names or values with spaces still work.
    """
    # Rejoin everything after the keyword and scan for an operator
    expression = " ".join(tokens[1:])

    found_op = None
    for op in FILTER_OPERATORS:
        if op in expression:
            found_op = op
            break

    if found_op is None:
        raise ParseError(
            f"'filter' requires an operator ({', '.join(FILTER_OPERATORS)}).\n"
            f"  Got: filter {expression}\n"
            f"  Example: filter region = South"
        )

    # Split on the operator (max 1 split so value can contain the char)
    parts = expression.split(found_op, 1)
    column = parts[0].strip()
    value  = parts[1].strip()

    if not column:
        raise ParseError("'filter' is missing a column name.")
    if not value:
        raise ParseError("'filter' is missing a value.")

    return FilterNode(column=column, operator=found_op, value=value)


def parse_group_by(tokens: list[str]) -> GroupByNode:
    """
    Grammar:  group by <column>
    Tokens:   ["group", "by", "month"]
    """
    # tokens[0] == "group", tokens[1] should == "by"
    if len(tokens) < 3 or tokens[1].lower() != "by":
        raise ParseError(
            f"'group by' syntax error.\n"
            f"  Got: {' '.join(tokens)}\n"
            f"  Expected: group by <column>"
        )
    column = tokens[2]
    return GroupByNode(column=column)


def parse_aggregate(tokens: list[str]) -> AggregateNode:
    """
    Grammar:  sum <column>  |  avg <column>  |  count <column>
    Tokens:   ["sum", "revenue"]
    """
    func = tokens[0].lower()
    if func not in AGGREGATE_FUNCTIONS:
        raise ParseError(f"Unknown aggregation function: '{func}'")

    if len(tokens) != 2:
        raise ParseError(
            f"'{func}' expects exactly one column argument.\n"
            f"  Got: {' '.join(tokens)}\n"
            f"  Example: {func} revenue"
        )
    column = tokens[1]
    return AggregateNode(function=func, column=column)


def parse_chart(tokens: list[str]) -> ChartNode:
    """
    Grammar:  chart <type> <x_column> <y_column>
    Tokens:   ["chart", "bar", "month", "revenue"]
    """
    if len(tokens) != 4:
        raise ParseError(
            f"'chart' expects: chart <type> <x_column> <y_column>.\n"
            f"  Got: {' '.join(tokens)}\n"
            f"  Example: chart bar month revenue"
        )
    chart_type = tokens[1].lower()
    if chart_type not in CHART_TYPES:
        raise ParseError(
            f"Unknown chart type: '{chart_type}'.\n"
            f"  Supported types: {', '.join(CHART_TYPES)}"
        )
    return ChartNode(chart_type=chart_type, x_column=tokens[2], y_column=tokens[3])


# ── Dispatcher ────────────────────────────────────────────────────────────────

def parse_command(raw_command: str, step_number: int) -> object:
    """
    Given a single raw command string (already split from the pipeline),
    identify its type and return the corresponding AST node.
    """
    # Tokenise by splitting on whitespace
    tokens = raw_command.strip().split()

    if not tokens:
        raise ParseError(f"Step {step_number}: empty command.")

    keyword = tokens[0].lower()

    print(f"  Step {step_number}: parsing '{keyword}' command → tokens: {tokens}")

    if keyword == "load":
        return parse_load(tokens)
    elif keyword == "filter":
        return parse_filter(tokens)
    elif keyword == "group":
        return parse_group_by(tokens)
    elif keyword in AGGREGATE_FUNCTIONS:
        return parse_aggregate(tokens)
    elif keyword == "chart":
        return parse_chart(tokens)
    else:
        raise ParseError(
            f"Step {step_number}: unknown command keyword '{keyword}'.\n"
            f"  Supported: load, filter, group by, sum, avg, count, chart"
        )


# ── Main entry point ──────────────────────────────────────────────────────────

def parse(source: str) -> PipelineNode:
    """
    Parse a full BizLang pipeline string and return a PipelineNode AST.

    Args:
        source: The complete BizLang expression, e.g.
                "load sales.csv | filter region = South | sum revenue"

    Returns:
        A PipelineNode containing all parsed step nodes in order.

    Raises:
        ParseError: if any step does not match the grammar.
    """
    print("\n── Parsing BizLang Input ──────────────────────────────────────")
    print(f"  Input: {source.strip()}\n")

    # Step 1: Split into individual commands on the pipe character
    raw_commands = source.strip().split("|")

    if not raw_commands:
        raise ParseError("Input is empty — nothing to parse.")

    print(f"  Found {len(raw_commands)} pipeline step(s):")

    # Step 2: Parse each command into an AST node
    steps = []
    for i, raw in enumerate(raw_commands, start=1):
        node = parse_command(raw.strip(), i)
        steps.append(node)
        print(f"    → {repr(node)}")

    print()

    # Step 3: Wrap in a PipelineNode
    pipeline = PipelineNode(steps=steps)
    return pipeline
