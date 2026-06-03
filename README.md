# BizLang

> Analyze any dataset with plain-English commands. No SQL, no Python, just results.

![BizLang Demo](demo.gif)

BizLang is a **pipeline-style domain-specific language (DSL)** that compiles plain-English analytics commands into executable Python. Type a query in the interactive REPL and get back a token breakdown, abstract syntax tree, execution plan, data table, chart, and a human-readable summary — all in one pass.

---

## Quick Start

```bash
git clone https://github.com/brendenarcher733/BIZLANG
cd BIZLANG
pip install -r requirements.txt
python main.py
```

---

## How It Works

```
Your Query
    │
    ▼  Lexer         tokenize into typed tokens with position info
    ▼  Parser        build an Abstract Syntax Tree (AST)
    ▼  Validator     semantic checks: load-first, group-before-agg, chart-last
    ▼  Planner       generate a human-readable execution plan
    ▼  Executor      run pandas operations directly — no temp files
    ▼  Code Gen      emit a standalone Python script as a side-artifact
    ▼  REPL          display tokens · AST · plan · results · chart · summary
```

Every step is surfaced to the user. BizLang is designed to be **transparent** — not a black box.

---

## Language

Commands are chained with `|` (pipe). Each command is one transformation step.

```
load sample_data/sales.csv
    | filter region = West AND revenue > 100
    | group by month
    | sum revenue
    | sort revenue desc
    | chart bar month revenue
```

### Command Reference

| Command | Syntax | Example |
|---------|--------|---------|
| **load** | `load <file.csv>` | `load sales.csv` |
| **filter** | `filter <col> <op> <val> [AND\|OR ...]` | `filter region = West AND revenue > 50` |
| **group by** | `group by <column>` | `group by month` |
| **sum / avg / count** | `sum\|avg\|count <column>` | `sum revenue` |
| **sort** | `sort <column> [asc\|desc]` | `sort revenue desc` |
| **display** | `display [n]` | `display 10` |
| **export** | `export <file.csv\|file.json>` | `export results.json` |
| **chart** | `chart bar\|line\|pie <x> <y>` | `chart bar month revenue` |

**Operators:** `=`  `!=`  `>`  `<`  `>=`  `<=`  
**Logic:** `AND`  `OR` (chain multiple filter conditions)  
**Chart types:** `bar`  `line`  `pie`

---

## REPL Commands

| Command | Description |
|---------|-------------|
| `/help` | Show the language reference |
| `/demos` | Show 5 runnable example queries |
| `/code` | Show generated Python for the last query |
| `/clear` | Clear the screen |
| `/quit` | Exit |

---

## Error Messages

BizLang reports errors with column-level precision — the same standard as production compilers:

```
╭─ Parse Error ──────────────────────────────────────────────────╮
│  Step 2 · chart: unsupported type 'scatter'.                   │
│    Supported: bar, line, pie                                   │
│                                                                │
│    load sales.csv | chart scatter month revenue                │
│                           ^                                    │
│    column 22                                                   │
╰────────────────────────────────────────────────────────────────╯
```

---

## Architecture

```
bizlang/
├── lexer.py        Tokenizer — source string → typed Token list
├── ast_nodes.py    AST node classes (Load, Filter, GroupBy, Aggregate,
│                   Sort, Display, Export, Chart, Pipeline)
├── parser.py       Recursive parser — tokens → PipelineNode AST
│                   + semantic validation (load-first, group-before-agg)
├── executor.py     Execution engine — AST → pandas operations (no subprocess)
├── planner.py      Execution planner — AST → human-readable plan steps
├── codegen.py      Code generator — AST → standalone Python script
├── cli.py          Rich interactive REPL
├── main.py         Entry point
└── tests/
    ├── test_lexer.py     19 tests — token types, operators, positions, errors
    ├── test_parser.py    27 tests — all commands, validation rules, error cases
    ├── test_executor.py  26 tests — load/filter/group/sort/export correctness
    └── test_codegen.py   16 tests — generated Python validity and correctness
```

---

## Test Suite

```
88 tests · 4 modules · ~0.3s
```

```bash
python -m pytest -v
```

---

## Grammar (EBNF)

```ebnf
pipeline      = command , { "|" , command } ;
command       = load_cmd | filter_cmd | groupby_cmd | aggregate_cmd
              | sort_cmd | display_cmd | export_cmd | chart_cmd ;

load_cmd      = "load" , filename ;
filter_cmd    = "filter" , condition , { ( "AND" | "OR" ) , condition } ;
condition     = column , operator , value ;
groupby_cmd   = "group" , "by" , column ;
aggregate_cmd = ( "sum" | "avg" | "count" ) , column ;
sort_cmd      = "sort" , column , [ "asc" | "desc" ] ;
display_cmd   = "display" , [ number ] ;
export_cmd    = "export" , filename ;
chart_cmd     = "chart" , ( "bar" | "line" | "pie" ) , column , column ;

operator      = "=" | "!=" | ">" | "<" | ">=" | "<=" ;
filename      = identifier , ".csv" | identifier , ".json" ;
```

---

## Pipeline Rules

| Rule | Reason |
|------|--------|
| `load` must be first | Every pipeline needs a data source |
| `group by` must precede aggregation | Matches pandas `.groupby().agg()` semantics |
| `chart` must be last | Visualization is always a terminal step |

---

## Design Notes

**Why pipe syntax?**  
Mirrors Unix pipelines — data analysts already think this way. It also makes parsing trivial: split on `|`, parse each segment independently.

**Why a hand-written parser over PLY/ANTLR?**  
The grammar is simple enough that a dispatcher-based parser is clearer and has zero dependencies. Every parse function maps directly to one grammar rule.

**Why direct execution over subprocess?**  
The executor runs pandas in-process, capturing per-step row counts and snapshots. This enables the live summary, display checkpoints, and scalar results — none of which are possible with a subprocess model.

**Why deferred `group by` code generation?**  
Pandas requires `groupby()` and `.agg()` to be chained. `GroupByNode` stores the column without emitting code; `AggregateNode` picks it up and emits the full call. This keeps generated code idiomatic.
