from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RulePolicy(BaseModel):
    enabled_rules: List[str] = Field(default_factory=list)
    disabled_rules: List[str] = Field(default_factory=list)
    enabled_categories: List[str] = Field(default_factory=list)
    severity_overrides: Dict[str, Literal["P0", "P1", "P2", "P3"]] = Field(default_factory=dict)


class RuleSuppression(BaseModel):
    rule_id: str
    scope: Literal["global", "statement"] = "global"
    statement_index: Optional[int] = Field(default=None, ge=1)


class SQLRequest(BaseModel):
    sql: str
    mode: Literal["rule", "ai", "hybrid"] = "hybrid"
    dialect: Optional[str] = "generic"
    max_issues: int = Field(default=20, ge=1, le=100)
    policy: Optional[RulePolicy] = None
    suppressions: List[RuleSuppression] = Field(default_factory=list)
    baseline_issues: List[Dict] = Field(default_factory=list)


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
    policy: Optional[RulePolicy] = None
    suppressions: List[RuleSuppression] = Field(default_factory=list)
    baseline_issues: List[Dict] = Field(default_factory=list)
