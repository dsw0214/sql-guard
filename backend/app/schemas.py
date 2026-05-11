from typing import Literal, Optional

from pydantic import BaseModel, Field


class SQLRequest(BaseModel):
    sql: str
    mode: Literal["rule", "ai", "hybrid"] = "hybrid"
    dialect: Optional[str] = "generic"
    max_issues: int = Field(default=20, ge=1, le=100)


class ExplainRequest(BaseModel):
    sql: str
    dialect: Optional[str] = "generic"


class MRReviewRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    diff: str
    mode: Literal["rule", "ai", "hybrid"] = "hybrid"
    dialect: Optional[str] = "generic"
    max_issues: int = Field(default=50, ge=1, le=200)
    max_sql: int = Field(default=20, ge=1, le=100)
