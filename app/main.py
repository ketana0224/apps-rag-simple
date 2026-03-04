import logging
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.aoai_client import generate_answer_with_aoai
from app.rag_placeholder import search as rag_placeholder_search

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="apps-rag-simple", version="0.1.0")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search")
def search(request: SearchRequest) -> dict:
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query must not be empty")

    logger.info("search request received")

    try:
        response = rag_placeholder_search(query)
        generated_answer, used_aoai = generate_answer_with_aoai(
            query=query,
            results=response.get("results", []),
            fallback_answer=response.get("answer", ""),
        )
        response["answer"] = generated_answer
        if used_aoai:
            response["source"] = "rag+aoai"

        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("search failed")
        raise HTTPException(status_code=500, detail="internal server error")
