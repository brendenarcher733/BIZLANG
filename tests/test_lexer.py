import pytest
from lexer import tokenize, TokenType, LexError


def _types(source: str) -> list[TokenType]:
    return [t.type for t in tokenize(source) if t.type is not TokenType.EOF]


# ── Token types ───────────────────────────────────────────────────────────────

def test_load_keyword():
    assert tokenize("load")[0].type is TokenType.LOAD


def test_all_keywords_recognised():
    cases = {
        "load": TokenType.LOAD,       "filter":  TokenType.FILTER,
        "group": TokenType.GROUP,     "by":      TokenType.BY,
        "sum":   TokenType.SUM,       "avg":     TokenType.AVG,
        "count": TokenType.COUNT,     "sort":    TokenType.SORT,
        "display": TokenType.DISPLAY, "export":  TokenType.EXPORT,
        "chart": TokenType.CHART,     "select":  TokenType.SELECT,
        "having": TokenType.HAVING,   "and":     TokenType.AND,
        "or":    TokenType.OR,        "asc":     TokenType.ASC,
        "desc":  TokenType.DESC,
    }
    for word, expected in cases.items():
        assert tokenize(word)[0].type is expected, f"'{word}' should be {expected.name}"


def test_select_keyword():
    assert tokenize("select")[0].type is TokenType.SELECT


def test_having_keyword():
    assert tokenize("having")[0].type is TokenType.HAVING


def test_comma_separator():
    tokens = [t for t in tokenize("a, b, c") if t.type is not TokenType.EOF]
    comma_count = sum(1 for t in tokens if t.type is TokenType.COMMA)
    assert comma_count == 2


def test_comma_role_label():
    tok = tokenize(",")[0]
    assert tok.type is TokenType.COMMA
    assert tok.role() == "separator"


def test_keywords_case_insensitive():
    assert tokenize("LOAD")[0].type is TokenType.LOAD
    assert tokenize("Filter")[0].type is TokenType.FILTER


def test_identifier():
    tok = tokenize("region")[0]
    assert tok.type is TokenType.IDENTIFIER
    assert tok.value == "region"


def test_filepath_as_single_identifier():
    tok = tokenize("sample_data/sales.csv")[0]
    assert tok.type is TokenType.IDENTIFIER
    assert tok.value == "sample_data/sales.csv"


# ── Operators ─────────────────────────────────────────────────────────────────

def test_all_operators():
    src = "= != > < >= <="
    expected = [TokenType.EQ, TokenType.NEQ, TokenType.GT,
                TokenType.LT, TokenType.GTE, TokenType.LTE]
    assert _types(src) == expected


def test_two_char_operators_not_split():
    # ">=" must produce GTE, not GT + EQ
    assert _types(">=") == [TokenType.GTE]
    assert _types("<=") == [TokenType.LTE]
    assert _types("!=") == [TokenType.NEQ]


def test_pipe_separator():
    types = _types("load a.csv | filter x = 1")
    assert TokenType.PIPE in types


# ── Numbers ───────────────────────────────────────────────────────────────────

def test_integer_token():
    tok = tokenize("42")[0]
    assert tok.type is TokenType.NUMBER
    assert tok.value == "42"


def test_float_token():
    tok = tokenize("3.14")[0]
    assert tok.type is TokenType.NUMBER
    assert tok.value == "3.14"


def test_negative_number():
    tok = tokenize("-5")[0]
    assert tok.type is TokenType.NUMBER
    assert tok.value == "-5"


# ── Quoted strings ────────────────────────────────────────────────────────────

def test_double_quoted_string_strips_quotes():
    tokens = [t for t in tokenize('"New York"') if t.type is not TokenType.EOF]
    assert tokens[0].type is TokenType.IDENTIFIER
    assert tokens[0].value == "New York"


def test_single_quoted_string():
    tok = tokenize("'hello world'")[0]
    assert tok.value == "hello world"


def test_unterminated_string_raises_lex_error():
    with pytest.raises(LexError, match="Unterminated"):
        tokenize('"unclosed')


# ── Token metadata ────────────────────────────────────────────────────────────

def test_token_position_is_tracked():
    tokens = tokenize("load sales.csv")
    assert tokens[0].pos == 0
    assert tokens[1].pos == 5   # "sales.csv" starts at index 5


def test_token_role_labels():
    assert tokenize("load")[0].role()    == "keyword"
    assert tokenize("region")[0].role()  == "identifier"
    assert tokenize("=")[0].role()       == "operator"
    assert tokenize("100")[0].role()     == "number"
    assert tokenize("|")[0].role()       == "separator"


# ── Errors ────────────────────────────────────────────────────────────────────

def test_unexpected_character_raises_lex_error():
    with pytest.raises(LexError, match="Unexpected"):
        tokenize("load @file.csv")


def test_eof_token_always_present():
    tokens = tokenize("load")
    assert tokens[-1].type is TokenType.EOF
