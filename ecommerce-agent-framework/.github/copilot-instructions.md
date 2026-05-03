**Project Overview**:
- **Purpose**: 电商客服框架（RAG + FastAPI），将商家文档接入本地向量库以支持基于知识的问答与工作流。
- **Key folders**: `app/`（核心逻辑），`app/knowledge/`（文档解析与接入），`app/rag/`（向量/检索层），`data/merchants/`（商家数据与向量库），`data/evaluation_sets/`（实验/基准）。

**Big Picture Architecture**:
- Ingestion pipeline: `app/knowledge/document_parser.py` -> `app/knowledge/chunking.py` -> `app/knowledge/ingestion.py` -> `app/rag/vector_store.py`.
- Vector store naming: each merchant gets its own local Chroma collection named by `merchant_id` (see `get_or_create_chroma()` in `app/rag/vector_store.py`).
- Embeddings: default uses `OpenAIEmbeddings()` in `ingestion.py` unless an `embeddings` param is passed.
- Retrieval & RAG: `app/rag/` is where retrievers, rerankers, and embedder wrappers belong (files may be stubs). Keep retrieval logic merchant-scoped (isolation by collection name).

**Developer Workflows (how to run common tasks)**:
- Ingest documents for merchant X (python API): call `app/knowledge/ingestion.ingest_merchant_documents(merchant_id, merchant_dir, embeddings)`; default merchant_dir resolves to `data/merchants/{merchant_id}`.
- To re-create vector DB for tests: remove `data/merchants/{merchant_id}/vector_store/*` (or `data/vector_stores/{merchant_id}` depending on `persist_root`) then re-run ingestion.
- Data files live under `data/merchants/{merchant_id}/`:
  - raw docs -> `raw_docs/` (PDF/DOCX/CSV/TXT),
  - products -> `products/` (CSV catalogs),
  - vector_store -> `vector_store/` (persisted assets).

**Project-specific conventions & patterns**:
- File parsing: `DocumentParser.load_merchant_data()` returns list of `{"source": filename, "content": text}`. Downstream functions expect this precise shape.
- Chunking: `split_documents()` returns list of `{"text": chunk_text, "metadata": {"source": filename, "chunk_index": i}}` and ingestion expects `text`/`metadatas` lists for `chroma.add_texts()`.
- Merchant isolation: all vector operations use the `merchant_id` as collection_name and dedicated persist directory — do not reuse a global collection across merchants.
- Embeddings injection: functions accept an `embeddings` argument for testing or swapping providers (mockable for unit tests).

**Integration points & external deps**:
- LangChain: `RecursiveCharacterTextSplitter`, `Chroma` wrapper, and `OpenAIEmbeddings` used across `app/knowledge` and `app/rag`.
- Document libs: `pypdf` (`PdfReader`) and `python-docx` (`Document`) are used for parsing; `pandas` for CSV/Excel.
- Runtime expectations: code assumes a Python environment with these packages installed (see `requirements.txt` at repo root).

**Concrete examples / gotchas**:
- Example ingestion call:
  - `from app.knowledge.ingestion import ingest_merchant_documents`
  - `ingest_merchant_documents('merchant_a')`  # reads `data/merchants/merchant_a`
- When adding CSV product catalogs, ingestion will convert table rows into flattened text via `parse_excel_csv()` — keep product CSV columns simple and well-named.
- If you need deterministic tests for embeddings, pass a mock `embeddings` implementing `embed_documents`/`embed_query` to `ingest_merchant_documents`.
- Parser limitations: `document_parser.parse_pdf()` uses `pypdf`. Ensure actual PDF binaries (not plain-text renamed to .pdf) are placed in `raw_docs/` if you expect reliable extraction.

**Where to look first when editing features**:
- Business logic / request handling: `app/main.py`, `app/engine.py` (entrypoints).
- Knowledge ingestion: `app/knowledge/document_parser.py`, `app/knowledge/chunking.py`, `app/knowledge/ingestion.py`.
- Vector persistence: `app/rag/vector_store.py` (collection naming and `persist_directory`).

**Short checklist for PRs touching ingestion or RAG**:
- Preserve merchant isolation (collection names and directories).
- Keep `DocumentParser` output shape unchanged; add new filetypes via `load_merchant_data()` only.
- Add unit/mini-integration tests that run ingestion with a small `products` CSV and text files and a mock embeddings object.

如果需要，我可以把本指南精简为更短的条目或加入更多示例命令（例如如何在本地重建 Chroma、如何用 mock embeddings 运行单元测试）。请告诉我哪些部分需要更详细的示例或补充。