# schemas.py

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class InitRequest(BaseModel):
    dimensions: int = Field(..., gt=0, description="Number of dimensions")


class InitResponse(BaseModel):
    message: str
    dimensions: int


class SetItemRequest(BaseModel):
    coords: List[str] = Field(..., description="List of coordinate keys")
    value: Any


class GetItemResponse(BaseModel):
    coords: List[str]
    value: Any


class DeleteItemRequest(BaseModel):
    coords: List[str]


class SliceRequest(BaseModel):
    prefix: List[str] = Field(
        default_factory=list,
        description="Optional coordinate prefix for slicing"
    )


class SliceResponse(BaseModel):
    prefix: List[str]
    data: Any


class InfoResponse(BaseModel):
    dimensions: Optional[int]
    initialized: bool
