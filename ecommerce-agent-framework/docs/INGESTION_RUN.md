# Ingestion: install & run

Prerequisites
- Create and activate a Python virtual environment.
- Ensure `requirements.txt` is installed when you want to run the full stack.

Quick install (minimal for tests):

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
pip install pytest
```

Run the ingestion script for a merchant (reads `data/merchants/{merchant_id}`):

```bash
# from repo root
python -c "from app.knowledge.ingestion import ingest_merchant_documents; print(ingest_merchant_documents('merchant_a'))"
```

Run unit tests (the test suite mocks heavy external deps):

```bash
pytest -q
```

Notes
- If you want to avoid calling OpenAI during development, pass a mock `embeddings` object to `ingest_merchant_documents`.
- Real PDF/DOCX files must be binary files produced by Word/PDF exporters; placeholders in text form will not parse correctly.
