"""Pydantic request/response models for the RAG endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestDocument(BaseModel):
    """A single source document to chunk, embed, and store."""

    source: str = Field(..., min_length=1, description="Stable identifier, e.g. file name or URL.")
    title: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    documents: list[IngestDocument] = Field(..., min_length=1)
    chunk_size: int = Field(800, ge=100, le=4000, description="Approx chars per chunk.")
    chunk_overlap: int = Field(120, ge=0, le=1000)


class IngestResponse(BaseModel):
    ingested_documents: int
    ingested_chunks: int


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: int
    source: str
    title: str
    chunk_index: int
    score: float = Field(..., description="Fused reciprocal-rank-fusion score.")
    vector_similarity: float = Field(..., description="Cosine similarity to the query (0..1).")
    snippet: str
    content: str


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


class Citation(BaseModel):
    source: str
    chunk_id: int
    title: str
    score: float


class AnswerRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    low_confidence: bool = Field(
        ..., description="True when retrieval is weak — route to a human (HITL)."
    )
    confidence: float = Field(..., description="Best evidence score in [0,1].")


# --- Document extraction (Prompt 3) ----------------------------------------


class InvoiceLineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None


class InvoiceExtraction(BaseModel):
    """Structured fields pulled from an invoice/form document."""

    vendor: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = Field(default=None, description="ISO date (YYYY-MM-DD) if parsed.")
    due_date: str | None = Field(default=None, description="ISO date (YYYY-MM-DD) if parsed.")
    currency: str | None = Field(default=None, description="ISO 4217 code, e.g. USD, EUR.")
    total: float | None = None
    line_items: list[InvoiceLineItem] = Field(default_factory=list)


class ExtractResponse(BaseModel):
    extraction: InvoiceExtraction
    low_confidence: bool = Field(
        ..., description="True when required fields are missing — route to a human (HITL)."
    )
    missing_fields: list[str] = Field(default_factory=list)
    persisted: bool = Field(..., description="Whether a row was written to app.invoices.")
    invoice_id: int | None = None
