from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, settings
from .runtime import CreditRuntime
from .schemas import (
    AccountInput,
    HealthResponse,
    ModelInfo,
    PackagedAccount,
    ReviewQueue,
    ScoreResponse,
)


def create_app(
    artifact_dir: Path | str | None = None,
    runtime: CreditRuntime | None = None,
) -> FastAPI:
    app_settings = Settings(artifact_dir=artifact_dir) if artifact_dir else settings
    load_error: str | None = None
    if runtime is None:
        try:
            runtime = CreditRuntime(app_settings.artifact_dir, app_settings.review_capacity)
        except Exception as error:
            load_error = str(error)

    application = FastAPI(title="Credit-account Review Prioritization API", version="0.1.0")
    application.state.runtime = runtime
    application.state.load_error = load_error
    application.state.settings = app_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def require_runtime(request: Request) -> CreditRuntime:
        current: CreditRuntime | None = request.app.state.runtime
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Credit model artifacts are unavailable. Run the credit-risk notebook or "
                    f"npm run prepare:credit. {request.app.state.load_error or ''}"
                ).strip(),
            )
        return current

    @application.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        current: CreditRuntime | None = request.app.state.runtime
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Credit model artifacts are unavailable. Run the credit-risk notebook or "
                    f"npm run prepare:credit. {request.app.state.load_error or ''}"
                ).strip(),
            )
        return HealthResponse(
            status="ok",
            service=app_settings.service_name,
            model="loaded",
            model_version=str(current.card["model_version"]),
            packaged_accounts=len(current.accounts),
            artifacts=current.artifact_readiness(),
        )

    @application.get("/api/credit/model", response_model=ModelInfo)
    def model_info(current: CreditRuntime = Depends(require_runtime)) -> ModelInfo:
        return current.model_info()

    @application.get("/api/credit/samples", response_model=list[PackagedAccount])
    def samples(
        limit: int = Query(default=12, ge=1, le=24),
        current: CreditRuntime = Depends(require_runtime),
    ) -> list[PackagedAccount]:
        return current.samples(max(1, min(limit, 24)))

    @application.post("/api/credit/score", response_model=ScoreResponse)
    def score(
        payload: AccountInput,
        current: CreditRuntime = Depends(require_runtime),
    ) -> ScoreResponse:
        try:
            return current.score(payload)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    @application.get("/api/credit/review-queue", response_model=ReviewQueue)
    def review_queue(
        limit: int = Query(default=25, ge=1, le=100),
        review_cost: float | None = Query(default=None, ge=0, le=1_000_000),
        current: CreditRuntime = Depends(require_runtime),
    ) -> ReviewQueue:
        return current.review_queue(max(1, min(limit, 100)), review_cost)

    return application


app = create_app()
