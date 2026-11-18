from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import require_any, User
from backend.services.lineage_service import get_column_lineage
from backend.schemas.schemas import LineageResponse

router = APIRouter(prefix="/api/lineage", tags=["lineage"])

@router.get("/{table}/{column}", response_model=LineageResponse)
def get_lineage(
    table: str,
    column: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Retrieves the column-level lineage graph for a given target column.
    """
    try:
        graph = get_column_lineage(db, table, column)
        return graph
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lineage query failed: {e}"
        )
