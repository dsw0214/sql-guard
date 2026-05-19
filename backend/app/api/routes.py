from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.config import AppConfig
from app.schemas import ExplainRequest, MRReviewRequest, SQLRequest
from app.services.analyzer import analyze_sql
from app.services.explainer import explain_sql
from app.services.file_review import review_sql_attachment
from app.services.mr_review import review_merge_request

router = APIRouter()


def _require_api_auth(authorization: str | None = None, x_api_key: str | None = None) -> None:
    expected_token = AppConfig.api_auth_token()
    if not expected_token:
        return

    bearer_token = ""
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            bearer_token = value.strip()

    if bearer_token == expected_token or (x_api_key or "").strip() == expected_token:
        return

    raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/")
def health():
    return {
        "status": "ok",
        "features": ["rule", "ai", "hybrid", "explain", "mr-review"],
    }


@router.post("/review")
async def review(
    req: SQLRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    return await analyze_sql(
        req.sql,
        req.mode,
        req.dialect,
        req.max_issues,
        policy=req.policy.model_dump() if req.policy else None,
        suppressions=[item.model_dump() for item in req.suppressions],
        baseline_issues=req.baseline_issues,
        ci_gate=req.ci_gate.model_dump() if req.ci_gate else None,
    )


@router.post("/review/upload")
async def review_upload(
    file: UploadFile = File(...),
    mode: str = Form("hybrid"),
    dialect: str = Form("generic"),
    max_issues: int = Form(20),
    gate_max_allowed_severity: str = Form(""),
    gate_max_score: int = Form(-1),
    gate_max_total_issues: int = Form(-1),
    gate_fail_on_ai_error: bool = Form(False),
    gate_only_new_issues: bool = Form(False),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    if mode not in {"rule", "ai", "hybrid"}:
        raise HTTPException(status_code=400, detail="mode 仅支持 rule/ai/hybrid")

    if max_issues < 1 or max_issues > 200:
        raise HTTPException(status_code=400, detail="max_issues 取值范围为 1-200")

    ci_gate = {
        "max_allowed_severity": gate_max_allowed_severity.upper() if gate_max_allowed_severity else None,
        "max_score": gate_max_score if gate_max_score >= 0 else None,
        "max_total_issues": gate_max_total_issues if gate_max_total_issues >= 0 else None,
        "fail_on_ai_error": gate_fail_on_ai_error,
        "only_new_issues": gate_only_new_issues,
    }
    if ci_gate["max_allowed_severity"] not in {None, "P0", "P1", "P2", "P3"}:
        raise HTTPException(status_code=400, detail="gate_max_allowed_severity 仅支持 P0/P1/P2/P3")

    return await review_sql_attachment(
        file,
        mode=mode,
        dialect=dialect,
        max_issues=max_issues,
        ci_gate=ci_gate,
    )


@router.post("/explain")
def explain(
    req: ExplainRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    return explain_sql(req.sql, req.dialect)


@router.post("/gitlab/mr-review")
async def gitlab_mr_review(
    req: MRReviewRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    return await review_merge_request(
        title=req.title,
        description=req.description,
        diff=req.diff,
        mode=req.mode,
        dialect=req.dialect,
        max_issues=req.max_issues,
        max_sql=req.max_sql,
        policy=req.policy.model_dump() if req.policy else None,
        suppressions=[item.model_dump() for item in req.suppressions],
        baseline_issues=req.baseline_issues,
        ci_gate=req.ci_gate.model_dump() if req.ci_gate else None,
    )


@router.get("/config")
def config(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    if not AppConfig.config_endpoint_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    return AppConfig.config_view()
