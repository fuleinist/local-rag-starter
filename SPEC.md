# local-rag-starter — SPEC v1

## Mission
One-command batteries-included starter kit for fully local RAG — Ollama + Qdrant + ingestion pipeline + chat UI.

## Why
Setting up local RAG is a multi-step nightmare: install Ollama, pull a model, set up a vector DB, write an ingestion script, build a UI. Most tutorials are outdated or use cloud APIs.

## Usage
```bash
# Start everything
docker compose up

# Ingest documents
lrag add ./docs

# Ask questions from terminal
lrag ask "how does auth work?"

# Or open the web UI at http://localhost:3000
```

## Acceptance Criteria

### Docker Compose (MVP)
- [ ] `docker compose up` starts: Ollama, Qdrant, ingestion worker, chat UI
- [ ] Ollama auto-pulls a default embedding model (nomic-embed-text) and chat model (qwen2.5:3b)
- [ ] All services communicate via Docker network
- [ ] Volumes mounted for persistence (Qdrant data, Ollama models)

### CLI (`lrag`)
- [ ] `lrag add <path>` — ingests files (PDF, markdown, txt, code) into Qdrant
- [ ] `lrag ask <question>` — answers from ingested documents
- [ ] `lrag status` — shows service health and document count
- [ ] `lrag list` — lists ingested documents
- [ ] `lrag remove <id>` — deletes a document from index
- [ ] Cross-platform (Linux, macOS, Windows via Docker)

### Ingestion Worker (FastAPI)
- [ ] REST API for document ingestion
- [ ] Supports: PDF, markdown, plain text, code files
- [ ] Chunks documents semantically (by paragraphs/sections)
- [ ] Embeds chunks via Ollama (nomic-embed-text)
- [ ] Stores vectors in Qdrant with metadata (filename, source, chunk index)
- [ ] Watches a mounted directory for auto-ingestion

### Chat UI (Svelte/React)
- [ ] Chat interface with message history
- [ ] Shows source citations with document name and chunk excerpt
- [ ] Streaming responses from Ollama
- [ ] Dark/light mode
- [ ] Document list with delete capability

### Query Pipeline
- [ ] Embeds user query via Ollama
- [ ] Searches Qdrant for top-k similar chunks
- [ ] Constructs prompt with context + question
- [ ] Streams response from Ollama chat model
- [ ] Returns citations with source documents

## Tech Stack
- **Orchestration:** Docker Compose
- **Ingestion:** Python / FastAPI
- **Vector DB:** Qdrant
- **Embeddings:** Ollama (nomic-embed-text)
- **Chat Model:** Ollama (qwen2.5:3b)
- **UI:** Svelte (with Vite)
- **CLI:** Python (click or argparse)

## Architecture
```
local-rag-starter/
├── docker-compose.yml       # Service orchestration
├── ingestion-worker/        # FastAPI ingestion service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── ingest.py
├── chat-ui/                 # Svelte chat interface
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.svelte
│   │   ├── main.js
│   │   └── lib/
│   │       └── api.js
│   └── public/
├── lrag                     # CLI entrypoint (shell script wrapping docker)
├── SPEC.md
└── README.md
```

## Out of Scope (v1)
- Authentication / multi-user
- Web crawling / URL ingestion
- Image/OCR support
- Custom model configuration UI
- Kubernetes / non-Docker deployment
