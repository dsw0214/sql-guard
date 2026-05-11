from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import AppConfig
from app.schemas import ExplainRequest, MRReviewRequest, SQLRequest
from app.services.analyzer import analyze_sql
from app.services.explainer import explain_sql
from app.services.file_review import review_sql_attachment
from app.services.mr_review import review_merge_request

router = APIRouter()


@router.get("/")
def health():
    return {
        "status": "ok",
        "features": ["rule", "ai", "hybrid", "explain", "mr-review"],
    }


@router.post("/review")
async def review(req: SQLRequest):
    return await analyze_sql(req.sql, req.mode, req.dialect, req.max_issues)


@router.post("/review/upload")
async def review_upload(
    file: UploadFile = File(...),
    mode: str = Form("hybrid"),
    dialect: str = Form("generic"),
    max_issues: int = Form(20),
):
    if mode not in {"rule", "ai", "hybrid"}:
        raise HTTPException(status_code=400, detail="mode 仅支持 rule/ai/hybrid")

    if max_issues < 1 or max_issues > 200:
        raise HTTPException(status_code=400, detail="max_issues 取值范围为 1-200")

    return await review_sql_attachment(file, mode=mode, dialect=dialect, max_issues=max_issues)


@router.post("/explain")
def explain(req: ExplainRequest):
    return explain_sql(req.sql, req.dialect)


@router.post("/gitlab/mr-review")
async def gitlab_mr_review(req: MRReviewRequest):
    return await review_merge_request(
        title=req.title,
        description=req.description,
        diff=req.diff,
        mode=req.mode,
        dialect=req.dialect,
        max_issues=req.max_issues,
        max_sql=req.max_sql,
    )


@router.get("/config")
def config():
    return AppConfig.config_view()
