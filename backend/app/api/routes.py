from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from app.config import AppConfig
from app.schemas import ExplainRequest, MRReviewRequest, RuntimeAIConfigRequest, SQLRequest
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
    x_client_id: str | None = Header(default=None),
):
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    tokens = AppConfig.bind_request_client(x_client_id)
    try:
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
    finally:
        AppConfig.reset_request_client(tokens)


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
    x_client_id: str | None = Header(default=None),
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

    tokens = AppConfig.bind_request_client(x_client_id)
    try:
        return await review_sql_attachment(
            file,
            mode=mode,
            dialect=dialect,
            max_issues=max_issues,
            ci_gate=ci_gate,
        )
    finally:
        AppConfig.reset_request_client(tokens)


@router.post("/explain")
def explain(
    req: ExplainRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_client_id: str | None = Header(default=None),
):
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    tokens = AppConfig.bind_request_client(x_client_id)
    try:
        return explain_sql(req.sql, req.dialect)
    finally:
        AppConfig.reset_request_client(tokens)


@router.post("/gitlab/mr-review")
async def gitlab_mr_review(
    req: MRReviewRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_client_id: str | None = Header(default=None),
):
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    tokens = AppConfig.bind_request_client(x_client_id)
    try:
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
    finally:
        AppConfig.reset_request_client(tokens)


@router.get("/config")
def config(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_client_id: str | None = Header(default=None),
):
    if not AppConfig.config_endpoint_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    tokens = AppConfig.bind_request_client(x_client_id)
    try:
        return AppConfig.config_view()
    finally:
        AppConfig.reset_request_client(tokens)


@router.get("/config/ai")
def get_runtime_ai_config(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_client_id: str | None = Header(default=None),
):
    if not AppConfig.config_endpoint_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)
    return AppConfig.runtime_ai_config_view(client_id=x_client_id, mask_secret=True)


@router.post("/config/ai")
def update_runtime_ai_config(
    req: RuntimeAIConfigRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_client_id: str | None = Header(default=None),
):
    if not AppConfig.config_endpoint_enabled():
        raise HTTPException(status_code=404, detail="Not Found")
    _require_api_auth(authorization=authorization, x_api_key=x_api_key)

    payload = {}
    if req.provider is not None:
        payload["SQLGUARD_AI_PROVIDER"] = req.provider
    if req.ai_base_url is not None:
        payload["SQLGUARD_AI_BASE_URL"] = req.ai_base_url
    if req.ai_model is not None:
        payload["SQLGUARD_AI_MODEL"] = req.ai_model
    if req.ai_api_key is not None:
        payload["SQLGUARD_AI_API_KEY"] = req.ai_api_key
    if req.ai_http_timeout is not None:
        payload["SQLGUARD_AI_HTTP_TIMEOUT"] = req.ai_http_timeout
    if req.ollama_base_url is not None:
        payload["SQLGUARD_OLLAMA_BASE_URL"] = req.ollama_base_url
    if req.ollama_model is not None:
        payload["SQLGUARD_OLLAMA_MODEL"] = req.ollama_model
    if req.ollama_http_timeout is not None:
        payload["SQLGUARD_OLLAMA_HTTP_TIMEOUT"] = req.ollama_http_timeout

    return AppConfig.update_runtime_ai_config(payload, client_id=x_client_id)
