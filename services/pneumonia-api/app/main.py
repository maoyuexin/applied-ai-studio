from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, settings
from .runtime import PneumoniaRuntime
from .schemas import ModelInfo, ReviewQueue, SampleStudy, ScoreRequest, ScoreResponse


def create_app(
    artifact_dir: Path | str | None = None,
    notebook_dir: Path | str | None = None,
    runtime: PneumoniaRuntime | None = None,
) -> FastAPI:
    values = {}
    if artifact_dir is not None:
        values["artifact_dir"] = artifact_dir
    if notebook_dir is not None:
        values["notebook_dir"] = notebook_dir
    app_settings = Settings(**values) if values else settings
    load_error: str | None = None
    if runtime is None:
        try:
            runtime = PneumoniaRuntime(app_settings.notebook_dir, app_settings.artifact_dir)
        except Exception as error:
            load_error = str(error)

    application = FastAPI(
        title="Pediatric Chest X-ray Prioritization Teaching API",
        version="0.1.0",
    )
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

    def require_runtime(request: Request) -> PneumoniaRuntime:
        current: PneumoniaRuntime | None = request.app.state.runtime
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Pneumonia model artifacts are unavailable. Run the notebook or "
                    f"npm run prepare:pneumonia. {request.app.state.load_error or ''}"
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

    @application.get("/api/pneumonia/model", response_model=ModelInfo)
    def model_info(current: PneumoniaRuntime = Depends(require_runtime)) -> ModelInfo:
        return current.model_info()

    @application.get("/api/pneumonia/samples", response_model=list[SampleStudy])
    def samples(
        limit: int = 12,
        current: PneumoniaRuntime = Depends(require_runtime),
    ) -> list[SampleStudy]:
        return current.samples(max(1, min(limit, 12)))

    @application.post("/api/pneumonia/score", response_model=ScoreResponse)
    def score(
        payload: ScoreRequest,
        current: PneumoniaRuntime = Depends(require_runtime),
    ) -> ScoreResponse:
        try:
            return current.score(payload)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))

    @application.get("/api/pneumonia/review-queue", response_model=ReviewQueue)
    def review_queue(
        limit: int = 25,
        current: PneumoniaRuntime = Depends(require_runtime),
    ) -> ReviewQueue:
        return current.review_queue(max(1, min(limit, 100)))

    return application


app = create_app()