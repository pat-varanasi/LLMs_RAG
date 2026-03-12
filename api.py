from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any

from db import init_db, search_chunks

app = FastAPI(title="Embeddable Chatbot API (MVP)")

class ChatRequest(BaseModel):
    message: str
    top_k: int = 6

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]

@app.on_event("startup")
def _startup():
    init_db()

def build_answer(message: str, hits):
    """
    MVP answer: stitch together top passages with a short preface.
    Later we can replace this with an LLM prompt that uses these passages.
    """
    if not hits:
        return (
            "I couldn’t find anything relevant in the site content I indexed yet. "
            "Try rephrasing, or ask about a specific page/topic.",
            [],
        )

    # Basic grounded response: summarize by selecting top snippets
    bullets = []
    sources = []
    for (url, title, chunk, chunk_index) in hits:
        bullets.append(f"- {chunk}")
        sources.append({"url": url, "title": title, "chunk_index": chunk_index})

    answer = (
        "Here’s what I found on the site:\n\n"
        + "\n".join(bullets[:4])
        + "\n\nIf you want, tell me what you’re trying to do and I’ll narrow it down."
    )
    return answer, sources

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    hits = search_chunks(req.message, k=req.top_k)
    answer, sources = build_answer(req.message, hits)
    return {"answer": answer, "sources": sources}

@app.get("/health")
def health():
    return {"ok": True}
