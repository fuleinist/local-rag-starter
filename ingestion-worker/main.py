"""local-rag-starter ingestion worker — FastAPI service."""

import os
import hashlib
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from ingest import Ingestor

app = FastAPI(title="LRAG Ingestion Worker", version="1.0.0")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen2.5:3b")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "documents")
EMBED_DIM = 768  # nomic-embed-text

qdrant = QdrantClient(url=QDRANT_URL)
ingestor = Ingestor(qdrant, OLLAMA_URL, EMBED_MODEL, COLLECTION_NAME)


@app.on_event("startup")
async def startup():
    """Ensure Ollama models are pulled and Qdrant collection exists."""
    async with httpx.AsyncClient() as client:
        for model in [EMBED_MODEL, CHAT_MODEL]:
            try:
                r = await client.post(f"{OLLAMA_URL}/api/pull", json={"name": model}, timeout=300)
                r.raise_for_status()
            except Exception as e:
                print(f"Warning: could not pull model {model}: {e}")

    collections = qdrant.get_collections().collections
    if not any(c.name == COLLECTION_NAME for c in collections):
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )
        print(f"Created collection '{COLLECTION_NAME}'")


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]


class DocumentInfo(BaseModel):
    id: str
    filename: str
    chunks: int
    created_at: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/documents")
async def list_documents():
    """List all ingested documents with chunk counts."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    scroll = qdrant.scroll(
        collection_name=COLLECTION_NAME,
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )
    docs: dict[str, dict] = {}
    for point in scroll[0]:
        fname = point.payload.get("filename", "unknown")
        if fname not in docs:
            docs[fname] = {"id": fname, "filename": fname, "chunks": 0, "created_at": ""}
        docs[fname]["chunks"] += 1
        if point.payload.get("created_at"):
            docs[fname]["created_at"] = point.payload["created_at"]
    return list(docs.values())


@app.delete("/documents/{filename:path}")
async def delete_document(filename: str):
    """Delete all chunks for a given document."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    qdrant.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
        ),
    )
    return {"status": "deleted", "filename": filename}


@app.post("/ingest/file", summary="Ingest a single file")
async def ingest_file(file: UploadFile = File(...)):
    content = await file.read()
    chunks = ingestor.ingest_text(content.decode("utf-8", errors="replace"), file.filename or "unknown")
    return {"filename": file.filename, "chunks": len(chunks)}


@app.post("/ingest/path", summary="Ingest files from a server path")
async def ingest_path(path: str = Form(...)):
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, f"Path not found: {path}")

    results = []
    if p.is_file():
        chunks = ingestor.ingest_file(str(p))
        results.append({"path": str(p), "chunks": len(chunks)})
    else:
        for f in sorted(p.rglob("*")):
            if f.is_file() and f.suffix.lower() in {".md", ".txt", ".py", ".js", ".rs", ".go", ".pdf", ".csv", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".bat", ".ps1"}:
                chunks = ingestor.ingest_file(str(f))
                results.append({"path": str(f), "chunks": len(chunks)})
    return {"ingested": results}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """Answer a question using RAG over ingested documents."""
    # Embed the question
    async with httpx.AsyncClient() as client:
        emb_resp = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": req.question},
        )
        emb_resp.raise_for_status()
        embedding = emb_resp.json()["embedding"]

    # Search Qdrant
    search_result = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        limit=req.top_k,
        with_payload=True,
    )

    if not search_result:
        return AskResponse(answer="No relevant documents found.", sources=[])

    # Build context
    context_parts = []
    sources = []
    for i, hit in enumerate(search_result):
        text = hit.payload.get("text", "")
        fname = hit.payload.get("filename", "unknown")
        context_parts.append(f"[Source {i+1}: {fname}]\n{text}")
        sources.append({
            "filename": fname,
            "score": hit.score,
            "excerpt": text[:200],
        })

    context = "\n\n".join(context_parts)
    prompt = f"""You are a helpful assistant answering questions based on the provided documents.

Context:
{context}

Question: {req.question}

Answer the question using only the context above. If the context doesn't contain enough information, say so. Include citations like [Source 1], [Source 2] etc."""

    # Stream response from Ollama
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": CHAT_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        answer = resp.json()["response"]

    return AskResponse(answer=answer, sources=sources)


@app.post("/ask/stream")
async def ask_stream(req: AskRequest):
    """Answer a question using RAG with streaming response."""
    # Embed the question
    async with httpx.AsyncClient() as client:
        emb_resp = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": req.question},
        )
        emb_resp.raise_for_status()
        embedding = emb_resp.json()["embedding"]

    # Search Qdrant
    search_result = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        limit=req.top_k,
        with_payload=True,
    )

    if not search_result:
        async def no_results():
            yield "data: " + '{"type":"text","content":"No relevant documents found."}' + "\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_results(), media_type="text/event-stream")

    # Build context
    context_parts = []
    sources = []
    for i, hit in enumerate(search_result):
        text = hit.payload.get("text", "")
        fname = hit.payload.get("filename", "unknown")
        context_parts.append(f"[Source {i+1}: {fname}]\n{text}")
        sources.append({
            "filename": fname,
            "score": hit.score,
            "excerpt": text[:200],
        })

    context = "\n\n".join(context_parts)
    prompt = f"""You are a helpful assistant answering questions based on the provided documents.

Context:
{context}

Question: {req.question}

Answer the question using only the context above. If the context doesn't contain enough information, say so. Include citations like [Source 1], [Source 2] etc."""

    async def generate():
        # Send sources first
        yield "data: " + '{"type":"sources","content":' + __import__("json").dumps(sources) + "}\n\n"

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/generate",
                json={"model": CHAT_MODEL, "prompt": prompt, "stream": True},
                timeout=120,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = __import__("json").loads(line)
                        if "response" in chunk:
                            yield "data: " + __import__("json").dumps({"type": "text", "content": chunk["response"]}) + "\n\n"
                        if chunk.get("done"):
                            break
                    except Exception:
                        pass

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
