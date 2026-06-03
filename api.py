"""
BizLang REST API

Start:   uvicorn api:app --reload
Docs:    http://localhost:8000/docs
"""

import base64
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from executor import Executor, ExecutionError
from parser import parse, ParseError
from planner import plan
from validator import SchemaValidator, ValidationError


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BizLang API",
    description=(
        "Analyze any dataset with plain-English pipeline commands.\n\n"
        "**Quick example:**\n"
        "```\n"
        "load sample_data/sales.csv | filter region = West\n"
        "  | group by month | sum revenue | chart bar month revenue\n"
        "```"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    pipeline: str

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "pipeline": (
                    "load sample_data/sales.csv | filter region = South | "
                    "group by month | sum revenue | sort revenue desc | "
                    "chart bar month revenue"
                )
            }]
        }
    }


class StepInfo(BaseModel):
    operation:   str
    description: str
    rows_before: int
    rows_after:  int


class PlanStepInfo(BaseModel):
    step:        int
    operation:   str
    description: str


class QueryResponse(BaseModel):
    ok:             bool
    plan:           list[PlanStepInfo]
    pipeline_steps: list[StepInfo]
    columns:        list[str]
    row_count:      int
    results:        list[dict[str, Any]]
    scalars:        dict[str, float]
    chart:          Optional[str]       # "data:image/png;base64,..." or None
    exports:        list[str]
    elapsed_ms:     float


class DatasetInfo(BaseModel):
    name:   str
    path:   str
    format: str


# ── Shared execution helper ───────────────────────────────────────────────────

def _run(pipeline_str: str) -> QueryResponse:
    """Parse → validate → execute a pipeline. Raises HTTPException on any error."""

    try:
        pipeline = parse(pipeline_str)
    except ParseError as e:
        raise HTTPException(
            status_code=422,
            detail={"stage": "parse", "message": str(e), "column": e.pos},
        )

    try:
        SchemaValidator().validate(pipeline)
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail={"stage": "validation", "message": str(e)},
        )

    try:
        result = Executor().execute(pipeline)
    except ExecutionError as e:
        raise HTTPException(
            status_code=422,
            detail={"stage": "execution", "message": str(e)},
        )

    chart_data: Optional[str] = None
    if result.chart_path and os.path.exists(result.chart_path):
        with open(result.chart_path, "rb") as fh:
            chart_data = "data:image/png;base64," + base64.b64encode(fh.read()).decode()

    plan_steps = plan(pipeline)

    return QueryResponse(
        ok=True,
        plan=[
            PlanStepInfo(step=p.number, operation=p.operation, description=p.description)
            for p in plan_steps
        ],
        pipeline_steps=[
            StepInfo(
                operation=s.operation,
                description=s.description,
                rows_before=s.rows_before,
                rows_after=s.rows_after,
            )
            for s in result.steps
        ],
        columns=list(result.df.columns),
        row_count=len(result.df),
        results=result.df.to_dict(orient="records"),
        scalars=result.scalars,
        chart=chart_data,
        exports=result.exports,
        elapsed_ms=result.elapsed_ms,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", tags=["meta"])
def health():
    """Service health check."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/datasets", response_model=list[DatasetInfo], tags=["meta"])
def list_datasets():
    """List datasets available in the server's sample_data/ directory."""
    fmt = {".csv": "CSV", ".json": "JSON", ".xlsx": "Excel",
           ".xls": "Excel", ".tsv": "TSV"}
    results: list[DatasetInfo] = []
    base = Path("sample_data")
    if base.is_dir():
        for f in sorted(base.iterdir()):
            if f.suffix.lower() in fmt:
                results.append(DatasetInfo(
                    name=f.name, path=str(f), format=fmt[f.suffix.lower()]
                ))
    return results


@app.post("/query", response_model=QueryResponse, tags=["query"])
def query(req: QueryRequest):
    """
    Run a BizLang pipeline against a file on the server.

    The `load` command references a path on the server filesystem.
    Use **`/query/upload`** to supply your own file.
    """
    return _run(req.pipeline)


@app.post("/query/upload", response_model=QueryResponse, tags=["query"])
async def query_with_upload(
    pipeline: str = Form(
        ...,
        description=(
            "BizLang transformation steps — **without** a leading `load` command.  "
            "Example: `filter region = West | group by month | sum revenue`"
        ),
    ),
    file: UploadFile = File(
        ...,
        description="Dataset file — CSV, TSV, JSON, or Excel (.xlsx / .xls)",
    ),
):
    """
    Run a BizLang pipeline against an **uploaded** file.

    Omit the `load` step — the server prepends it automatically using the
    uploaded file.  Supported formats: CSV, TSV, JSON, Excel.
    """
    suffix = Path(file.filename or "upload.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        return _run(f'load "{tmp_path}" | {pipeline}')
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
