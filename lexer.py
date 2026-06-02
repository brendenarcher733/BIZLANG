from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenType(Enum):
    LOAD = auto();    FILTER = auto();  GROUP = auto();   BY = auto()
    SUM = auto();     AVG = auto();     COUNT = auto()
    SORT = auto();    DISPLAY = auto(); EXPORT = auto();  CHART = auto()
    AND = auto();     OR = auto();      ASC = auto();     DESC = auto()
    EQ = auto();      NEQ = auto();     GT = auto();      LT = auto()
    GTE = auto();     LTE = auto();     PIPE = auto()
    IDENTIFIER = auto(); NUMBER = auto(); EOF = auto()


_KEYWORDS: dict[str, TokenType] = {
    "load": TokenType.LOAD,       "filter": TokenType.FILTER,
    "group": TokenType.GROUP,     "by":     TokenType.BY,
    "sum":   TokenType.SUM,       "avg":    TokenType.AVG,
    "count": TokenType.COUNT,     "sort":   TokenType.SORT,
    "display": TokenType.DISPLAY, "export": TokenType.EXPORT,
    "chart": TokenType.CHART,     "and":    TokenType.AND,
    "or":    TokenType.OR,        "asc":    TokenType.ASC,
    "desc":  TokenType.DESC,
}

_OPERATORS: dict[str, TokenType] = {
    "!=": TokenType.NEQ, ">=": TokenType.GTE, "<=": TokenType.LTE,
    "=":  TokenType.EQ,  ">":  TokenType.GT,  "<":  TokenType.LT,
    "|":  TokenType.PIPE,
}

_ROLE: dict[TokenType, str] = {
    TokenType.LOAD: "keyword",    TokenType.FILTER: "keyword",
    TokenType.GROUP: "keyword",   TokenType.BY: "keyword",
    TokenType.SUM: "keyword",     TokenType.AVG: "keyword",
    TokenType.COUNT: "keyword",   TokenType.SORT: "keyword",
    TokenType.DISPLAY: "keyword", TokenType.EXPORT: "keyword",
    TokenType.CHART: "keyword",   TokenType.AND: "keyword",
    TokenType.OR: "keyword",      TokenType.ASC: "keyword",
    TokenType.DESC: "keyword",
    TokenType.EQ: "operator",     TokenType.NEQ: "operator",
    TokenType.GT: "operator",     TokenType.LT: "operator",
    TokenType.GTE: "operator",    TokenType.LTE: "operator",
    TokenType.PIPE: "separator",
    TokenType.IDENTIFIER: "identifier",
    TokenType.NUMBER: "number",
    TokenType.EOF: "eof",
}


@dataclass
class Token:
    type:  TokenType
    value: str
    pos:   int

    def role(self) -> str:
        return _ROLE.get(self.type, self.type.name.lower())

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r})"


class LexError(Exception):
    def __init__(self, message: str, pos: int = -1):
        super().__init__(message)
        self.pos = pos


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i, n = 0, len(source)

    while i < n:
        if source[i].isspace():
            i += 1
            continue

        # Two-char operators first (order matters)
        if i + 1 < n and source[i:i+2] in _OPERATORS:
            op = source[i:i+2]
            tokens.append(Token(_OPERATORS[op], op, i))
            i += 2
            continue

        # Single-char operators / pipe
        if source[i] in _OPERATORS:
            tokens.append(Token(_OPERATORS[source[i]], source[i], i))
            i += 1
            continue

        # Quoted string literals — tokenised as IDENTIFIER, quotes stripped
        if source[i] in ('"', "'"):
            quote = source[i]
            j = i + 1
            while j < n and source[j] != quote:
                j += 1
            if j >= n:
                raise LexError(f"Unterminated string literal at position {i}", pos=i)
            tokens.append(Token(TokenType.IDENTIFIER, source[i+1:j], i))
            i = j + 1
            continue

        # Numbers (optional leading minus)
        if source[i].isdigit() or (source[i] == '-' and i+1 < n and source[i+1].isdigit()):
            j = i + (1 if source[i] == '-' else 0)
            while j < n and (source[j].isdigit() or source[j] == '.'):
                j += 1
            tokens.append(Token(TokenType.NUMBER, source[i:j], i))
            i = j
            continue

        # Identifiers, keywords, and file paths (letters + _ . / -)
        if source[i].isalpha() or source[i] == '_':
            j = i
            while j < n and (source[j].isalnum() or source[j] in ('_', '.', '/', '-')):
                j += 1
            word = source[i:j]
            ttype = _KEYWORDS.get(word.lower(), TokenType.IDENTIFIER)
            tokens.append(Token(ttype, word, i))
            i = j
            continue

        raise LexError(f"Unexpected character '{source[i]}'", pos=i)

    tokens.append(Token(TokenType.EOF, "", n))
    return tokens
