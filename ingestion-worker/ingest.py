"""Document ingestion — chunking, embedding, and storing in Qdrant."""

import os
import hashlib
import time
from pathlib import Path
from typing import Optional

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct


class Ingestor:
    """Handles document chunking, embedding, and Qdrant storage."""

    def __init__(self, qdrant: QdrantClient, ollama_url: str, embed_model: str, collection: str):
        self.qdrant = qdrant
        self.ollama_url = ollama_url
        self.embed_model = embed_model
        self.collection = collection

    def chunk_text(self, text: str, filename: str, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
        """Split text into overlapping chunks by paragraphs."""
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) < chunk_size:
                current += "\n\n" + para if current else para
            else:
                if current:
                    chunks.append(current)
                current = para

        if current:
            chunks.append(current)

        # If still too large, split by sentences
        result = []
        for chunk in chunks:
            if len(chunk) <= chunk_size:
                result.append(chunk)
            else:
                # Split oversized chunk
                words = chunk.split()
                sub = ""
                for w in words:
                    if len(sub) + len(w) + 1 > chunk_size:
                        result.append(sub)
                        sub = w
                    else:
                        sub += " " + w if sub else w
                if sub:
                    result.append(sub)

        # Apply overlap between adjacent chunks
        if overlap > 0 and len(result) > 1:
            overlapped = [result[0]]
            for i in range(1, len(result)):
                prev = result[i - 1]
                curr = result[i]
                # Take last `overlap` chars from previous chunk as prefix
                overlap_text = prev[-overlap:] if len(prev) > overlap else prev
                overlapped.append(overlap_text + "\n" + curr)
            result = overlapped

        return [
            {"text": c, "filename": filename, "chunk_index": i}
            for i, c in enumerate(result)
        ]

    def ingest_text(self, text: str, filename: str) -> list[PointStruct]:
        """Ingest raw text: chunk, embed, store."""
        chunks = self.chunk_text(text, filename)
        points = []

        for chunk in chunks:
            # Embed
            resp = httpx.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": chunk["text"]},
                timeout=30,
            )
            resp.raise_for_status()
            embedding = resp.json()["embedding"]

            point_id = hashlib.md5(f"{filename}:{chunk['chunk_index']}".encode()).hexdigest()
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "text": chunk["text"],
                    "filename": chunk["filename"],
                    "chunk_index": chunk["chunk_index"],
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            ))

        if points:
            self.qdrant.upsert(collection_name=self.collection, points=points)

        return points

    def ingest_file(self, filepath: str) -> list[PointStruct]:
        """Ingest a file from disk."""
        path = Path(filepath)
        if not path.exists():
            return []

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(str(path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as e:
                print(f"Error reading PDF {filepath}: {e}")
                return []
        else:
            try:
                text = path.read_text("utf-8", errors="replace")
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
                return []

        return self.ingest_text(text, path.name)
