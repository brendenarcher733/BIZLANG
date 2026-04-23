# BizLang — Business Analytics Domain-Specific Language

A mini compiler project for a Programming Languages / Compilers course.  
BizLang lets you write plain-English style analytics commands that are parsed
into an AST and compiled into executable Python (pandas + matplotlib).

---

## Project Overview

BizLang is a pipeline-style DSL. Commands are chained with `|` (pipe), just
like a Unix shell. Each command corresponds to one data transformation step:

```
load sales.csv | filter region = South | group by month | sum revenue | chart bar month revenue
```

The system has three stages:

```
BizLang Source → Parser → AST → Code Generator → Python Script → Execution
```

---

## Project Structure

```
bizlang/
│── main.py           Entry point — runs the full pipeline
│── parser.py         Tokenises and parses BizLang into an AST
│── ast_nodes.py      AST node class definitions
│── codegen.py        Walks the AST, emits pandas + matplotlib code
│── output.py         Generated file (created at runtime)
│── chart_output.png  Generated chart (created at runtime)
│── sample_data/
│   └── sales.csv     Sample business data for demos
└── README.md
```

---

## DSL Grammar (EBNF)

```ebnf
(* Top-level pipeline — one or more commands separated by "|" *)
pipeline    = command , { "|" , command } ;

(* A command is one of the supported keywords *)
command     = load_cmd
            | filter_cmd
            | groupby_cmd
            | aggregate_cmd
            | chart_cmd ;

(* Load a CSV file *)
load_cmd    = "load" , filename ;
filename    = string , ".csv" ;

(* Filter rows by a column value *)
filter_cmd  = "filter" , column , operator , value ;
operator    = "=" | "!=" | ">" | "<" | ">=" | "<=" ;

(* Group rows by a column *)
groupby_cmd = "group" , "by" , column ;

(* Aggregate a numeric column *)
aggregate_cmd = ( "sum" | "avg" | "count" ) , column ;

(* Render a chart — must be the last command *)
chart_cmd   = "chart" , chart_type , column , column ;
chart_type  = "bar" | "line" | "pie" ;

(* Terminals *)
column      = letter , { letter | digit | "_" } ;
value       = string | number ;
string      = { letter | digit | "_" | "-" } ;
number      = [ "-" ] , digit , { digit } , [ "." , { digit } ] ;
```

### Pipeline Rules

| Rule | Description |
|------|-------------|
| `load` must be first | Every pipeline must start with a load command |
| `group by` before aggregation | groupby must precede sum / avg / count |
| `chart` must be last | The chart command must be the final step |

---

## AST Node Classes

Defined in `ast_nodes.py`. Each node maps to one BizLang command.

| Node | Fields | Example BizLang |
|------|--------|-----------------|
| `LoadNode` | `filename` | `load sales.csv` |
| `FilterNode` | `column`, `operator`, `value` | `filter region = South` |
| `GroupByNode` | `column` | `group by month` |
| `AggregateNode` | `function`, `column` | `sum revenue` |
| `ChartNode` | `chart_type`, `x_column`, `y_column` | `chart bar month revenue` |
| `PipelineNode` | `steps` (list of nodes above) | *(root node)* |

Every node has a `to_dict()` method so it can be printed as JSON.

---

## How to Run

### 1. Install dependencies

```bash
pip install pandas matplotlib
```

### 2. Run the demo

```bash
python main.py
```

This will:
- Parse the hardcoded BizLang input
- Print the AST as JSON
- Print the generated Python code
- Ask if you want to execute the generated code
- Save a chart to `chart_output.png`

### 3. Try different examples

Open `main.py` and change the `BIZLANG_INPUT` variable:

```python
BIZLANG_INPUT = DEMO_1   # filter + bar chart
BIZLANG_INPUT = DEMO_2   # avg + pie chart
BIZLANG_INPUT = DEMO_3   # numeric filter + line chart
```

---

## Example Input

```
load sample_data/sales.csv | filter region = South | group by month | sum revenue | chart bar month revenue
```

---

## Example Output

### Parser output

```
── Parsing BizLang Input ──────────────────────────────────────
  Input: load sample_data/sales.csv | filter region = South | group by month | sum revenue | chart bar month revenue

  Found 5 pipeline step(s):
  Step 1: parsing 'load' command  → LoadNode(filename='sample_data/sales.csv')
  Step 2: parsing 'filter' command → FilterNode(column='region', operator='=', value='South')
  Step 3: parsing 'group' command  → GroupByNode(column='month')
  Step 4: parsing 'sum' command    → AggregateNode(function='sum', column='revenue')
  Step 5: parsing 'chart' command  → ChartNode(type='bar', x='month', y='revenue')
```

### AST (JSON)

```json
{
  "node": "PipelineNode",
  "steps": [
    { "node": "LoadNode",      "filename": "sample_data/sales.csv" },
    { "node": "FilterNode",    "column": "region", "operator": "=", "value": "South" },
    { "node": "GroupByNode",   "column": "month" },
    { "node": "AggregateNode", "function": "sum", "column": "revenue" },
    { "node": "ChartNode",     "chart_type": "bar", "x_column": "month", "y_column": "revenue" }
  ]
}
```

### Generated Python code

```python
# Generated by BizLang Code Generator
import pandas as pd
import matplotlib.pyplot as plt

# Step: load
df = pd.read_csv("sample_data/sales.csv")

# Step: filter region = South
df = df[df["region"] == "South"]

# Step: group by month
_group_col = "month"

# Step: sum revenue (with group by month)
df = df.groupby(_group_col)["revenue"].sum().reset_index()

# Step: chart bar month revenue
plt.figure(figsize=(8, 5))
plt.bar(df["month"], df["revenue"], color="steelblue", edgecolor="white")
plt.xlabel("Month")
plt.ylabel("Revenue")
plt.title("Revenue by Month")
plt.tight_layout()
plt.savefig("chart_output.png")
plt.show()
```

### Execution output

```
Loaded data:
   month region  revenue  units
0    Jan  South      100     10
4    Feb  South       90      8
8    Mar  South      150     18
12   Apr  South      200     24

After group by + sum:
  month  revenue
0   Apr      200
1   Feb       90
2   Jan      100
3   Mar      150

Chart saved to chart_output.png
```

---

## Design Decisions

**Why a pipe-separated pipeline?**  
It mirrors Unix pipelines which data analysts already understand intuitively.
It also makes parsing trivial: split on `|`, parse each chunk independently.

**Why hand-written parser instead of PLY/ANTLR?**  
The grammar is simple enough that a hand-written recursive descent (actually
just a dispatcher) is clearer and has zero external dependencies. It also
makes the code generation logic more transparent for a course project.

**Why deferred `group by` code generation?**  
Pandas requires `groupby()` and `.agg()` to be chained together.
The `GroupByNode` stores the column name without emitting code yet.
The `AggregateNode` visitor picks it up and emits the full `groupby().sum()`
call. This keeps the generated code idiomatic.

**Why save to `output.py` then execute?**  
It makes the compiler pipeline visible: you can inspect the generated code
before running it, which is pedagogically clearer than `exec()`-ing it in memory.

---

## Supported Commands

| Command | Syntax | Example |
|---------|--------|---------|
| Load    | `load <file.csv>` | `load sales.csv` |
| Filter  | `filter <col> <op> <val>` | `filter region = South` |
| Group   | `group by <col>` | `group by month` |
| Sum     | `sum <col>` | `sum revenue` |
| Average | `avg <col>` | `avg revenue` |
| Count   | `count <col>` | `count units` |
| Chart   | `chart <type> <x> <y>` | `chart bar month revenue` |

**Operators:** `=`  `!=`  `>`  `<`  `>=`  `<=`  
**Chart types:** `bar`  `line`  `pie`

---

## Limitations

- **One filter per pipeline.** Multiple filters would require extending
  the grammar and adding logical operators (`AND`, `OR`).
- **Single aggregation per pipeline.** You cannot do `sum revenue | avg units`
  in one pipeline — run separate pipelines instead.
- **No joins.** BizLang works with a single loaded CSV at a time.
- **No column aliasing.** You cannot rename columns in the DSL.
- **CSV only.** The `load` command only accepts `.csv` files.
- **No ORDER BY.** Results are returned in the order pandas produces them.

These are intentional scope decisions for a student project — each limitation
points to a clear extension path for future work.
