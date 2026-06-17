"""Invoice/form extraction: PDF text -> validated structured fields.

Provider selection (``LLM_PROVIDER``):
  * ``openai`` / ``anthropic`` — LLM constrained to a strict JSON schema.
  * ``local`` (or any provider with a placeholder key) — deterministic regex
    heuristic, so the pipeline is demoable and testable offline.

Whatever the provider, the result is validated against ``InvoiceExtraction`` and
then scored for missing fields by the calling service.
"""

from __future__ import annotations

import io
import json
import re
from datetime import date, datetime

import httpx

from app.config import get_settings
from app.models import InvoiceExtraction, InvoiceLineItem

# --- JSON schema handed to the LLM ----------------------------------------

INVOICE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": ["string", "null"]},
        "invoice_number": {"type": ["string", "null"]},
        "invoice_date": {"type": ["string", "null"], "description": "ISO YYYY-MM-DD"},
        "due_date": {"type": ["string", "null"], "description": "ISO YYYY-MM-DD"},
        "currency": {"type": ["string", "null"], "description": "ISO 4217 code"},
        "total": {"type": ["number", "null"]},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "amount": {"type": ["number", "null"]},
                },
                "required": ["description"],
            },
        },
    },
    "required": ["vendor", "invoice_number", "invoice_date", "currency", "total", "line_items"],
}

_EXTRACT_INSTRUCTION = (
    "You extract structured data from an invoice or form. Return ONLY JSON matching the "
    "given schema. Use null for any field not present in the document — never guess or "
    "fabricate. Dates must be ISO YYYY-MM-DD. If the document is not an invoice, return "
    "nulls and an empty line_items array."
)

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}


# --- PDF text --------------------------------------------------------------


def extract_text_from_pdf(data: bytes) -> str:
    """Extract raw text from a PDF byte payload."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def parse_date(value: str | None) -> str | None:
    """Best-effort parse to ISO YYYY-MM-DD; return None if unrecognised."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    # Already ISO-ish?
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError:
            return None
    return None


# --- Local heuristic extractor --------------------------------------------


def _money(text: str) -> float | None:
    cleaned = text.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _local_extract_invoice(text: str) -> InvoiceExtraction:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    invoice_number = None
    m = re.search(
        r"inv(?:oice)?\.?\s*(?:number|no\.?|num|#)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9\-/]*)",
        text,
        re.IGNORECASE,
    )
    if m:
        invoice_number = m.group(1)

    invoice_date = None
    m = re.search(r"invoice\s*date\s*[:#]?\s*([0-9][0-9A-Za-z/.\- ]{5,})", text, re.IGNORECASE)
    if m:
        invoice_date = parse_date(m.group(1))

    due_date = None
    m = re.search(r"due\s*date\s*[:#]?\s*([0-9][0-9A-Za-z/.\- ]{5,})", text, re.IGNORECASE)
    if m:
        due_date = parse_date(m.group(1))

    currency = None
    total = None
    m = re.search(
        r"(?<!sub)(?:total|amount\s*due|balance\s*due)\s*[:#]?\s*"
        r"([A-Z]{3})?\s*([$€£¥])?\s*([0-9][0-9,]*(?:\.[0-9]{2})?)",
        text,
        re.IGNORECASE,
    )
    if m:
        total = _money(m.group(3))
        if m.group(1):
            currency = m.group(1).upper()
        elif m.group(2):
            currency = _CURRENCY_SYMBOLS.get(m.group(2))

    # Line items in the explicit "<qty> x <desc> @ <unit> = <amount>" form.
    line_items: list[InvoiceLineItem] = []
    for qty, desc, unit, amount in re.findall(
        r"(\d+(?:\.\d+)?)\s*x\s*(.+?)\s*@\s*([\d,]+(?:\.\d{2})?)\s*=\s*([\d,]+(?:\.\d{2})?)",
        text,
        re.IGNORECASE,
    ):
        line_items.append(
            InvoiceLineItem(
                description=desc.strip(),
                quantity=_money(qty),
                unit_price=_money(unit),
                amount=_money(amount),
            )
        )

    # Vendor: first content line that isn't a bare document label.
    vendor = None
    for ln in lines:
        if re.fullmatch(r"(invoice|receipt|tax invoice)", ln, re.IGNORECASE):
            continue
        vendor = ln
        break
    # Only trust the vendor guess on documents that look invoice-like.
    if invoice_number is None and total is None:
        vendor = None

    return InvoiceExtraction(
        vendor=vendor,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        currency=currency,
        total=total,
        line_items=line_items,
    )


# --- LLM extractors --------------------------------------------------------


def _is_placeholder(key: str | None) -> bool:
    return not key or "replace" in key.lower()


def _coerce(payload: dict[str, object]) -> InvoiceExtraction:
    ext = InvoiceExtraction.model_validate(payload)
    ext.invoice_date = parse_date(ext.invoice_date)
    ext.due_date = parse_date(ext.due_date)
    return ext


def _openai_extract_invoice(text: str, model: str, key: str) -> InvoiceExtraction:
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": f"{_EXTRACT_INSTRUCTION}\nSchema: {json.dumps(INVOICE_JSON_SCHEMA)}",
                },
                {"role": "user", "content": text},
            ],
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return _coerce(json.loads(resp.json()["choices"][0]["message"]["content"]))


def _anthropic_extract_invoice(text: str, model: str, key: str) -> InvoiceExtraction:
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        json={
            "model": model,
            "max_tokens": 1024,
            "system": f"{_EXTRACT_INSTRUCTION}\nSchema: {json.dumps(INVOICE_JSON_SCHEMA)}",
            "messages": [
                {"role": "user", "content": f"{text}\n\nReturn only the JSON object."}
            ],
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    body = resp.json()["content"][0]["text"]
    match = re.search(r"\{.*\}", body, re.DOTALL)
    return _coerce(json.loads(match.group(0) if match else body))


def extract_invoice(text: str) -> InvoiceExtraction:
    """Extract structured invoice fields using the configured provider."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "openai" and not _is_placeholder(settings.openai_api_key):
        assert settings.openai_api_key is not None
        return _openai_extract_invoice(text, settings.llm_model, settings.openai_api_key)
    if provider == "anthropic" and not _is_placeholder(settings.anthropic_api_key):
        assert settings.anthropic_api_key is not None
        return _anthropic_extract_invoice(text, settings.llm_model, settings.anthropic_api_key)
    return _local_extract_invoice(text)
