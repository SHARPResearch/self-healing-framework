# services/llm-copilot

LangChain RCA + conversational copilot service (Doc1 §2 "LLM Copilot / RCA Engine").

**Tech**: Python, LangChain, FAISS (or pgvector via TimescaleDB — Doc1 §1 notes pgvector replaces
a standalone FAISS/Prometheus TSDB for app queries), `sentence-transformers`.

**Status**: scaffold only (`.gitkeep`).

**Build next** (`docs/Doc3_Execution_Guide.md` Phase 1 & 7, in order):
1. `uv init --python 3.11` + `uv add langchain langchain-openai faiss-cpu sentence-transformers`
2. `rag/indexer.py` — subscribes to Redis Streams, embeds anomaly events with
   `sentence-transformers/all-MiniLM-L6-v2`
3. `rag/retriever.py` — similarity search over indexed telemetry documents
4. `chains/rca_chain.py`, `chains/postmortem_chain.py`
5. `api/chat.py` — `POST /chat`, streaming SSE response

Requires an LLM API key in `.env` (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`) — never commit it;
in the cluster it comes from a Kubernetes Secret mounted as an env var.
