"""FastAPI entrypoint for the tools microservice.

Endpoints:
  GET  /health         liveness + provider check
  POST /ingest         ingest text documents (JSON) into the RAG store
  POST /ingest/file    ingest a single uploaded text/PDF file
  POST /search         hybrid retrieval (pgvector + full-text, RRF-fused)
  POST /answer         grounded answer with citations + low-confidence flag

The /extract document endpoint is added in Prompt 3.
"""

from __future__ import annotations

import psycopg
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app import __version__, extraction, rag, service
from app.config import get_settings
from app.models import (
    AnswerRequest,
    AnswerResponse,
    ExtractResponse,
    IngestDocument,
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
)

app = FastAPI(
    title="AI Ops Control Plane — Tools",
    version=__version__,
    summary="RAG, document extraction, and embedding utilities called by n8n over HTTP.",
)


class HealthResponse(BaseModel):
    """Liveness payload."""

    status: str
    version: str
    llm_provider: str
    embedding_model: str


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness probe. Reports the configured providers so n8n can sanity-check wiring."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        llm_provider=settings.llm_provider,
        embedding_model=settings.embedding_model,
    )


@app.post("/ingest", response_model=IngestResponse, tags=["rag"])
def ingest(req: IngestRequest) -> IngestResponse:
    """Chunk, embed, and upsert text documents into the knowledge base."""
    try:
        return service.ingest_documents(req)
    except psycopg.OperationalError as exc:  # database unreachable
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.post("/ingest/file", response_model=IngestResponse, tags=["rag"])
async def ingest_file(
    file: UploadFile = File(...),
    source: str | None = Form(default=None),
    title: str | None = Form(default=None),
) -> IngestResponse:
    """Ingest a single uploaded file (.pdf extracted with pypdf, else decoded as UTF-8)."""
    data = await file.read()
    name = file.filename or "upload"
    if name.lower().endswith(".pdf"):
        text = rag.read_pdf_text(data)
    else:
        text = data.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(status_code=422, detail="no extractable text in upload")
    doc = IngestDocument(source=source or name, title=title or name, text=text)
    try:
        return service.ingest_documents(IngestRequest(documents=[doc]))
    except psycopg.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.post("/search", response_model=SearchResponse, tags=["rag"])
def search(req: SearchRequest) -> SearchResponse:
    """Hybrid retrieval: pgvector cosine + Postgres full-text, fused with RRF."""
    try:
        return service.search(req)
    except psycopg.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.post("/answer", response_model=AnswerResponse, tags=["rag"])
def answer(req: AnswerRequest) -> AnswerResponse:
    """Answer strictly from retrieved context; flag low confidence for HITL escalation."""
    try:
        return service.answer(req)
    except psycopg.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc


@app.post("/extract", response_model=ExtractResponse, tags=["documents"])
async def extract(file: UploadFile = File(...)) -> ExtractResponse:
    """Extract structured fields from an invoice/form PDF and persist valid invoices."""
    data = await file.read()
    name = file.filename or "upload"
    if name.lower().endswith(".pdf"):
        text = extraction.extract_text_from_pdf(data)
    else:
        text = data.decode("utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(status_code=422, detail="no extractable text in upload")
    try:
        return service.extract_invoice_document(text, source_file=name)
    except psycopg.OperationalError as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc
