"""
BizLang interactive REPL.

Runs the full pipeline for every query and displays:
  Token Breakdown · AST · Execution Plan · Step Results · Data Table · Summary
"""

import json
from typing import Optional

try:
    import readline
    readline.set_history_length(500)
except ImportError:
    pass

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich import box

from lexer import tokenize, LexError, TokenType
from parser import parse, ParseError
from executor import Executor, ExecutionResult, ExecutionError
from planner import plan
from codegen import CodeGenerator, CodeGenError
from ast_nodes import PipelineNode


# ── Colour palette ────────────────────────────────────────────────────────────

_ROLE_STYLE: dict[str, str] = {
    "keyword":    "bold cyan",
    "operator":   "bold yellow",
    "identifier": "white",
    "number":     "bold green",
    "separator":  "dim white",
}

_OP_ICON: dict[str, str] = {
    "LOAD":    "◈",
    "FILTER":  "◎",
    "GROUP BY": "⊞",
    "SUM":     "∑",
    "AVG":     "∅",
    "COUNT":   "#",
    "SORT":    "↕",
    "DISPLAY": "▦",
    "EXPORT":  "↗",
    "CHART":   "◉",
}

_DEMOS: list[tuple[str, str]] = [
    (
        "Revenue by month (South region)",
        "load sample_data/sales.csv | filter region = South | "
        "group by month | sum revenue | sort revenue desc | chart bar month revenue",
    ),
    (
        "Average revenue by region (pie chart)",
        "load sample_data/sales.csv | group by region | avg revenue | "
        "sort revenue desc | chart pie region revenue",
    ),
    (
        "High-value months (revenue > 100, line chart)",
        "load sample_data/sales.csv | filter revenue > 100 | "
        "group by month | sum revenue | chart line month revenue",
    ),
    (
        "Multi-filter: North region with high units",
        "load sample_data/sales.csv | filter region = North AND units > 14 | "
        "sort revenue desc | display",
    ),
    (
        "Export filtered data to CSV",
        "load sample_data/sales.csv | filter region = West | "
        "sort revenue desc | export west_results.csv",
    ),
]

_HELP_TEXT = """
[bold cyan]BizLang[/bold cyan] — Business Analytics DSL

[bold]Pipeline syntax[/bold]
  Commands are chained with [bold]|[/bold] (pipe).  Each command is one data step.

[bold]Commands[/bold]
  [cyan]load[/cyan] [dim]<file.csv>[/dim]                 Load a CSV dataset
  [cyan]filter[/cyan] [dim]<col> <op> <val>[/dim]          Filter rows  (ops: = != > < >= <=)
  [dim]         [/dim][cyan]AND[/cyan][dim]|[/dim][cyan]OR[/cyan] [dim]<col> <op> <val>[/dim]  Chain multiple conditions
  [cyan]group by[/cyan] [dim]<column>[/dim]               Group rows by a column
  [cyan]sum[/cyan] | [cyan]avg[/cyan] | [cyan]count[/cyan] [dim]<column>[/dim]     Aggregate within groups
  [cyan]sort[/cyan] [dim]<column>[/dim] [cyan]asc[/cyan]|[cyan]desc[/cyan]         Sort results
  [cyan]display[/cyan] [dim][n][/dim]                     Show the current dataset
  [cyan]export[/cyan] [dim]<file.csv|file.json>[/dim]       Save results to a file
  [cyan]chart[/cyan] [cyan]bar[/cyan]|[cyan]line[/cyan]|[cyan]pie[/cyan] [dim]<x> <y>[/dim]   Render a chart

[bold]REPL commands[/bold]
  [bold]/demos[/bold]   Show example queries
  [bold]/code[/bold]    Show generated Python for the last query
  [bold]/clear[/bold]   Clear the screen
  [bold]/help[/bold]    Show this message
  [bold]/quit[/bold]    Exit  (also: q  exit)
"""


class BizLangCLI:
    def __init__(self):
        self.console    = Console(highlight=False)
        self._executor  = Executor()
        self._last_pipeline:  Optional[PipelineNode]   = None
        self._last_result:    Optional[ExecutionResult] = None

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> None:
        self._banner()
        self._repl()

    # ── Banner ────────────────────────────────────────────────────────────────

    def _banner(self) -> None:
        self.console.print()
        self.console.print(Panel(
            Text.assemble(
                ("BizLang", "bold white"),
                ("  ·  ", "dim"),
                ("Business Analytics DSL", "cyan"),
                ("\nAnalyze any dataset with plain-English commands. No code required.", "dim"),
            ),
            border_style="blue",
            padding=(1, 4),
            expand=False,
        ))
        self.console.print(
            "  Type a pipeline or [bold]/help[/bold] · "
            "[bold]/demos[/bold] to explore · [bold]/quit[/bold] to exit\n",
            style="dim",
        )

    # ── REPL loop ─────────────────────────────────────────────────────────────

    def _repl(self) -> None:
        while True:
            try:
                raw = self.console.input("[bold blue]bizlang[/bold blue] [dim]›[/dim] ")
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]Goodbye.[/dim]")
                break

            source = raw.strip()
            if not source:
                continue

            if source.lower() in ("q", "quit", "exit", "/quit", "/exit", "/q"):
                self.console.print("[dim]Goodbye.[/dim]")
                break
            elif source.startswith("/"):
                self._handle_meta(source)
            else:
                self._run_pipeline(source)

    # ── Meta commands ─────────────────────────────────────────────────────────

    def _handle_meta(self, cmd: str) -> None:
        match cmd.lower():
            case "/help" | "/h":
                self.console.print(Panel(_HELP_TEXT, border_style="dim", title="Help"))
            case "/demos" | "/d":
                self._show_demos()
            case "/code":
                self._show_generated_code()
            case "/clear" | "/c":
                self.console.clear()
                self._banner()
            case _:
                self.console.print(f"[red]Unknown command:[/red] {cmd}  — type [bold]/help[/bold]")

    # ── Pipeline execution ────────────────────────────────────────────────────

    def _run_pipeline(self, source: str) -> None:
        self.console.print()

        # 1 · Tokenize ────────────────────────────────────────────────────────
        try:
            tokens = tokenize(source)
        except LexError as e:
            self._error("Tokenization Error", str(e), source=source, pos=e.pos)
            return

        self._show_tokens(tokens)

        # 2 · Parse ───────────────────────────────────────────────────────────
        try:
            pipeline = parse(source)
        except ParseError as e:
            self._error("Parse Error", str(e), source=source, pos=e.pos)
            return

        self._last_pipeline = pipeline
        self._show_ast(pipeline)

        # 3 · Execution plan ──────────────────────────────────────────────────
        self._show_plan(pipeline)

        # 4 · Execute ─────────────────────────────────────────────────────────
        self.console.print("  [dim]Executing…[/dim]")
        try:
            result = self._executor.execute(pipeline)
        except ExecutionError as e:
            self._error("Execution Error", str(e))
            return

        self._last_result = result

        # 5 · Step results ────────────────────────────────────────────────────
        self._show_step_results(result)

        # 6 · Final dataset — skip if a DISPLAY step already rendered it
        already_displayed = any(s.snapshot is not None for s in result.steps)
        if not result.df.empty and not result.scalars and not already_displayed:
            self._show_dataframe(result)

        # 7 · Chart notification ──────────────────────────────────────────────
        if result.chart_path:
            self.console.print(
                f"  [bold green]✓[/bold green]  Chart saved → "
                f"[bold]{result.chart_path}[/bold]"
            )

        # 8 · Export notification ─────────────────────────────────────────────
        for path in result.exports:
            self.console.print(
                f"  [bold green]✓[/bold green]  Exported → [bold]{path}[/bold]"
            )

        # 9 · Summary ─────────────────────────────────────────────────────────
        self._show_summary(result)
        self.console.print()

    # ── Display helpers ───────────────────────────────────────────────────────

    def _show_tokens(self, tokens) -> None:
        visible = [t for t in tokens if t.type is not TokenType.EOF]

        table = Table(
            title=f"Token Breakdown  [dim]·  {len(visible)} tokens[/dim]",
            title_style="bold",
            box=box.SIMPLE_HEAD,
            border_style="dim",
            show_header=True,
            header_style="bold dim",
            padding=(0, 1),
        )
        table.add_column("#",     style="dim",   justify="right", width=4)
        table.add_column("Value", min_width=18)
        table.add_column("Type",  min_width=13,  style="dim")
        table.add_column("Role",  min_width=12)

        for i, tok in enumerate(visible, 1):
            role   = tok.role()
            style  = _ROLE_STYLE.get(role, "white")
            table.add_row(
                str(i),
                f"[{style}]{tok.value}[/{style}]",
                tok.type.name,
                role,
            )

        self.console.print(table)

    def _show_ast(self, pipeline: PipelineNode) -> None:
        ast_json = json.dumps(pipeline.to_dict(), indent=2)
        self.console.print(Panel(
            Syntax(ast_json, "json", theme="monokai", background_color="default"),
            title="[bold]Abstract Syntax Tree[/bold]",
            border_style="blue",
            padding=(0, 1),
        ))

    def _show_plan(self, pipeline: PipelineNode) -> None:
        steps = plan(pipeline)
        lines = Text()
        for s in steps:
            icon = _OP_ICON.get(s.operation, "→")
            lines.append(f"  {s.number:>2}  ", style="dim")
            lines.append(f"{icon} ", style="bold cyan")
            lines.append(f"{s.operation:<10}", style="bold white")
            lines.append(f"  {s.description}\n", style="white")

        self.console.print(Panel(
            lines,
            title="[bold]Execution Plan[/bold]",
            border_style="blue",
            padding=(0, 1),
        ))

    def _show_step_results(self, result: ExecutionResult) -> None:
        lines = Text()
        for s in result.steps:
            icon  = _OP_ICON.get(s.operation, "→")
            lines.append(f"  {icon} ", style="bold green")
            lines.append(f"{s.operation:<10}", style="bold dim")
            lines.append(f"  {s.description}\n")

            if s.snapshot is not None:
                # DISPLAY node — show inline table
                lines.append("\n")
                self.console.print(Panel(
                    lines,
                    title="[bold]Step Results[/bold]",
                    border_style="green",
                    padding=(0, 1),
                ))
                self._render_df_table(s.snapshot, title="Display Output")
                lines = Text()

        if str(lines):
            self.console.print(Panel(
                lines,
                title="[bold]Step Results[/bold]",
                border_style="green",
                padding=(0, 1),
            ))

    def _show_dataframe(self, result: ExecutionResult) -> None:
        MAX_ROWS = 50
        df = result.df
        truncated = len(df) > MAX_ROWS
        display_df = df.head(MAX_ROWS) if truncated else df
        caption = f"{len(df):,} rows" + (f"  (showing first {MAX_ROWS})" if truncated else "")
        self._render_df_table(display_df, title=f"Results  [dim]·  {caption}[/dim]")

    def _render_df_table(self, df, title: str = "Dataset") -> None:
        table = Table(
            title=title,
            title_style="bold",
            box=box.SIMPLE_HEAD,
            border_style="dim",
            show_header=True,
            header_style="bold cyan",
            padding=(0, 1),
        )
        for col in df.columns:
            table.add_column(str(col), justify="right" if df[col].dtype.kind in "iuf" else "left")

        for _, row in df.iterrows():
            cells = []
            for val in row:
                if isinstance(val, float):
                    cells.append(f"{val:,.2f}" if val != int(val) else f"{int(val):,}")
                elif isinstance(val, int):
                    cells.append(f"{val:,}")
                else:
                    cells.append(str(val))
            table.add_row(*cells)

        self.console.print(table)

    def _show_summary(self, result: ExecutionResult) -> None:
        lines: list[str] = []

        # Step-by-step recap
        for s in result.steps:
            lines.append(f"[bold green]✓[/bold green]  {s.description}")

        # Timing
        lines.append(f"\n[dim]Completed in {result.elapsed_ms:.1f} ms[/dim]")

        # Numeric insights from final dataframe
        df = result.df
        if not df.empty:
            num_cols = list(df.select_dtypes(include="number").columns)
            cat_cols = list(df.select_dtypes(exclude="number").columns)

            def _fmt(v: float) -> str:
                return f"{int(v):,}" if v == int(v) else f"{v:,.2f}"

            for col in num_cols:
                total  = df[col].sum()
                hi_val = df[col].max()
                lo_val = df[col].min()
                mean   = df[col].mean()

                lines.append(f"\n[bold dim]── {col} insights[/bold dim]")
                if cat_cols:
                    grp    = cat_cols[0]
                    hi_lbl = df.loc[df[col].idxmax(), grp]
                    lo_lbl = df.loc[df[col].idxmin(), grp]
                    lines.append(
                        f"   total [green]{_fmt(total)}[/green]  ·  "
                        f"highest [cyan]{hi_lbl}[/cyan] ({_fmt(hi_val)})  ·  "
                        f"lowest [cyan]{lo_lbl}[/cyan] ({_fmt(lo_val)})  ·  "
                        f"avg {_fmt(mean)}"
                    )
                else:
                    lines.append(
                        f"   total [green]{_fmt(total)}[/green]  ·  "
                        f"max {_fmt(hi_val)}  ·  min {_fmt(lo_val)}  ·  avg {_fmt(mean)}"
                    )

        # Scalar results (ungrouped aggregations)
        for label, val in result.scalars.items():
            lines.append(f"\n[bold dim]Result[/bold dim]  [bold]{label}[/bold] = [green]{val:,.4g}[/green]")

        body = Text.from_markup("\n".join(lines))
        self.console.print(Panel(
            body,
            title="[bold]Summary[/bold]",
            border_style="blue",
            padding=(1, 2),
        ))

    # ── Utility ───────────────────────────────────────────────────────────────

    def _show_demos(self) -> None:
        lines = Text()
        for i, (label, query) in enumerate(_DEMOS, 1):
            lines.append(f"  {i}.  ", style="dim")
            lines.append(f"{label}\n", style="bold white")
            lines.append(f"     {query}\n\n", style="cyan")
        self.console.print(Panel(lines, title="[bold]Example Queries[/bold]",
                                 border_style="dim", padding=(0, 1)))

    def _show_generated_code(self) -> None:
        if self._last_pipeline is None:
            self.console.print("[dim]No pipeline has been run yet.[/dim]")
            return
        try:
            code = CodeGenerator().generate(self._last_pipeline)
        except CodeGenError as e:
            self._error("Code Generation Error", str(e))
            return
        self.console.print(Panel(
            Syntax(code, "python", theme="monokai", background_color="default",
                   line_numbers=True),
            title="[bold]Generated Python[/bold]",
            border_style="blue",
            padding=(0, 1),
        ))

    def _error(self, title: str, message: str,
               source: str = "", pos: int = -1) -> None:
        from rich.text import Text
        body = Text()
        body.append(message + "\n", style="red")

        if source and pos >= 0:
            col = pos + 1   # 1-indexed, matches editor convention
            body.append(f"\n  {source}\n", style="dim")
            body.append("  " + " " * pos + "^\n", style="bold red")
            body.append(f"  column {col}", style="dim red")

        self.console.print(Panel(
            body,
            title=f"[bold red]{title}[/bold red]",
            border_style="red",
            padding=(0, 2),
        ))
