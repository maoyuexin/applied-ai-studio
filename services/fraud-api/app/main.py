from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, settings
from .runtime import FraudRuntime
from .schemas import ModelInfo, ReviewQueue, SampleTransaction, ScoreResponse, TransactionInput


def create_app(
    artifact_dir: Path | str | None = None,
    runtime: FraudRuntime | None = None,
) -> FastAPI:
    app_settings = Settings(artifact_dir=artifact_dir) if artifact_dir else settings
    load_error: str | None = None
    if runtime is None:
        try:
            runtime = FraudRuntime(app_settings.artifact_dir)
        except Exception as error:
            load_error = str(error)

    application = FastAPI(title="Card Transaction Fraud Detection API", version="0.1.0")
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

    def require_runtime(request: Request) -> FraudRuntime:
        current: FraudRuntime | None = request.app.state.runtime
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Fraud model artifacts are unavailable. Run the fraud notebook or "
                    f"npm run prepare:fraud. {request.app.state.load_error or ''}"
                ).strip(),
            )
        return current

    @application.get("/health")
    def health(request: Request) -> dict[str, str]:
        if request.app.state.runtime is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=request.app.state.load_error or "Model unavailable.",
            )
        return {"status": "ok", "service": app_settings.service_name, "model": "loaded"}

    @application.get("/api/fraud/model", response_model=ModelInfo)
    def model_info(current: FraudRuntime = Depends(require_runtime)) -> ModelInfo:
        return current.model_info()

    @application.get("/api/fraud/samples", response_model=list[SampleTransaction])
    def samples(
        limit: int = 12,
        current: FraudRuntime = Depends(require_runtime),
    ) -> list[SampleTransaction]:
        return current.samples(max(1, min(limit, 12)))

    @application.post("/api/fraud/score", response_model=ScoreResponse)
    def score(
        payload: TransactionInput,
        current: FraudRuntime = Depends(require_runtime),
    ) -> ScoreResponse:
        try:
            return current.score(payload)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    @application.get("/api/fraud/review-queue", response_model=ReviewQueue)
    def review_queue(
        limit: int = 25,
        current: FraudRuntime = Depends(require_runtime),
    ) -> ReviewQueue:
        return current.review_queue(max(1, min(limit, 100)))

    return application


app = create_app()