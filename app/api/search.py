from fastapi import APIRouter, Depends, HTTPException, Query

from app.clients.prowlarr import ProwlarrError
from app.dependencies import get_search_service
from app.models import SearchResult
from app.services.search import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
def search_movies(
    query: str = Query(min_length=1),
    search_service: SearchService = Depends(get_search_service),
) -> list[SearchResult]:
    """Search Prowlarr for movie torrents, most seeders first."""
    try:
        return search_service.search_movies(query)
    except ProwlarrError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
