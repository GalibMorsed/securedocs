from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models import User
from app.rag.embeddings import EmbeddingBudgetExceeded, EmbeddingError, EmbeddingProvider, TransientEmbeddingError, get_embedding_provider
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import search_documents

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> SearchResponse:
    try:
        provider: EmbeddingProvider = get_embedding_provider()
        results = search_documents(db, current_user, payload, provider, redis_client)
    except EmbeddingBudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (TransientEmbeddingError, EmbeddingError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SearchResponse(results=results)
