# local-rag-starter 🏠🧠

**One-command batteries-included starter kit for fully local RAG.**

Ollama + Qdrant + ingestion pipeline + chat UI. No cloud APIs. No API keys. Just `docker compose up`.

## Quick Start

```bash
# Clone and go
git clone https://github.com/fuleinist/local-rag-starter.git
cd local-rag-starter

# Start everything
docker compose up -d

# Ingest some documents
lrag add ./my-docs

# Ask questions
lrag ask "What does this project do?"

# Or open the web UI
open http://localhost:3000
```

## What's Inside

| Service | Port | Purpose |
|---------|------|---------|
| **Ollama** | 11434 | Local LLM (embeddings + chat) |
| **Qdrant** | 6333 | Vector database |
| **Ingestion Worker** | 8000 | Document chunking + embedding API |
| **Chat UI** | 3000 | Svelte web interface |

## CLI

```bash
lrag up              # Start all services
lrag down            # Stop all services
lrag status          # Check service health
lrag add ./docs      # Ingest files (PDF, md, txt, code)
lrag ask "question"  # Ask about your documents
lrag list            # List ingested documents
lrag remove <name>   # Delete a document
lrag logs            # Tail service logs
```

## Supported File Types

- Markdown (`.md`)
- Plain text (`.txt`)
- PDF (`.pdf`)
- Code: Python, JavaScript, Rust, Go, Shell, and more

## Architecture

```
                    ┌─────────────┐
                    │  Chat UI    │
                    │  :3000      │
                    └──────┬──────┘
                           │ HTTP
                    ┌──────▼──────┐
                    │  Ingestion  │
                    │  Worker     │◄──── lrag CLI
                    │  :8000      │
                    └──┬──────┬───┘
                       │      │
              ┌────────▼┐  ┌──▼────────┐
              │ Ollama  │  │  Qdrant   │
              │ :11434  │  │  :6333    │
              └─────────┘  └───────────┘
```

## Why Local RAG?

- **Privacy** — your documents never leave your machine
- **Free** — no API costs, no rate limits
- **Offline** — works without internet after initial model pull
- **Control** — swap models, tweak chunking, customize the pipeline

## License

MIT
