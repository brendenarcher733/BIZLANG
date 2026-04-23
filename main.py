# main.py
# ─────────────────────────────────────────────────────────────────────────────
# BizLang: Business Analytics DSL — Main Entry Point
#
# This file ties together the parser and code generator.
# It runs a hardcoded example that demonstrates the full pipeline:
#
#   BizLang source
#       → Parser (produces AST)
#       → Code Generator (produces Python source)
#       → Execute the generated code
#
# Run with:  python main.py
# ─────────────────────────────────────────────────────────────────────────────

import json
import os
import sys

from parser  import parse, ParseError
from codegen import CodeGenerator, CodeGenError


# ─────────────────────────────────────────────────────────────────────────────
# Demo inputs — uncomment the one you want to run
# ─────────────────────────────────────────────────────────────────────────────

DEMO_1 = (
    "load sample_data/sales.csv | "
    "filter region = South | "
    "group by month | "
    "sum revenue | "
    "chart bar month revenue"
)

DEMO_2 = (
    "load sample_data/sales.csv | "
    "group by region | "
    "avg revenue | "
    "chart pie region revenue"
)

DEMO_3 = (
    "load sample_data/sales.csv | "
    "filter revenue > 100 | "
    "group by month | "
    "sum revenue | "
    "chart line month revenue"
)

# ── Change this to DEMO_2 or DEMO_3 to try other examples ─────────────────
BIZLANG_INPUT = DEMO_1


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_section(title: str) -> None:
    """Print a visible section header to the console."""
    width = 65
    print("\n" + "═" * width)
    print(f"  {title}")
    print("═" * width)


def print_ast_json(pipeline) -> None:
    """Pretty-print the AST as indented JSON."""
    ast_dict = pipeline.to_dict()
    print(json.dumps(ast_dict, indent=2))


def save_generated_code(code: str, filename: str = "output.py") -> None:
    """Write the generated Python code to a file."""
    with open(filename, "w") as f:
        f.write(code)
    print(f"  Generated code saved to: {filename}")


def execute_generated_code(filename: str = "output.py") -> None:
    """
    Execute the generated Python script in a subprocess.
    This keeps the generated code's namespace separate from main.py.
    """
    print(f"\n  Executing {filename} ...\n")
    exit_code = os.system(f"{sys.executable} {filename}")
    if exit_code != 0:
        print(f"\n  ⚠ Execution finished with exit code {exit_code}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print_section("BizLang — Business Analytics DSL")
    print(f"\n  Input:\n  {BIZLANG_INPUT}\n")

    # ── Phase 1: Parse ────────────────────────────────────────────────────────
    print_section("Phase 1: Parsing")
    try:
        pipeline = parse(BIZLANG_INPUT)
    except ParseError as e:
        print(f"\n  PARSE ERROR: {e}")
        sys.exit(1)

    print("  Parse complete.\n")

    # ── Phase 2: AST ──────────────────────────────────────────────────────────
    print_section("Phase 2: Abstract Syntax Tree (AST)")
    print()
    print_ast_json(pipeline)

    # ── Phase 3: Code Generation ──────────────────────────────────────────────
    print_section("Phase 3: Code Generation")
    print()
    try:
        gen  = CodeGenerator()
        code = gen.generate(pipeline)
    except CodeGenError as e:
        print(f"\n  CODE GEN ERROR: {e}")
        sys.exit(1)

    # ── Phase 4: Print Generated Code ────────────────────────────────────────
    print_section("Phase 4: Generated Python Code")
    print()
    print(code)

    # ── Phase 5: Save + Execute ───────────────────────────────────────────────
    print_section("Phase 5: Save and Execute")
    save_generated_code(code, "output.py")

    answer = input("\n  Execute the generated code now? (y/n): ").strip().lower()
    if answer == "y":
        execute_generated_code("output.py")
    else:
        print("  Skipped execution. Run manually with:  python output.py")

    print_section("Done")
    print("  BizLang run complete.\n")


if __name__ == "__main__":
    main()
