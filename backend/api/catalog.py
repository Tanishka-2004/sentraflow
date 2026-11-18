from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.api.auth import require_any, User
from backend.models.models import CatalogDataset, CatalogColumn
from backend.schemas.schemas import CatalogDatasetResponse, CatalogColumnResponse
from typing import List, Optional

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

@router.get("/datasets", response_model=List[CatalogDatasetResponse])
def get_datasets(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Retrieves data catalog datasets.
    """
    datasets = db.query(CatalogDataset).offset((page - 1) * limit).limit(limit).all()
    return datasets

@router.get("/datasets/{dataset_id}", response_model=CatalogDatasetResponse)
def get_dataset_detail(
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Retrieves detailed metadata for a specific dataset including all its columns.
    """
    dataset = db.query(CatalogDataset).filter(CatalogDataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    return dataset

@router.get("/columns", response_model=List[CatalogColumnResponse])
def get_columns(
    dataset_id: Optional[int] = Query(None),
    is_pii: Optional[bool] = Query(None),
    sensitivity: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any)
):
    """
    Query columns in the catalog with optional filtering.
    """
    query = db.query(CatalogColumn)
    if dataset_id is not None:
        query = query.filter(CatalogColumn.dataset_id == dataset_id)
    if is_pii is not None:
        query = query.filter(CatalogColumn.is_pii == is_pii)
    if sensitivity:
        query = query.filter(CatalogColumn.sensitivity == sensitivity)
        
    return query.all()
