from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, settings
from .runtime import MaintenanceRuntime
from .schemas import (
    HealthResponse,
    ModelInfo,
    QueueResponse,
    SampleWindow,
    ScoreRequest,
    ScoreResponse,
)

UNAVAILABLE = (
    "Predictive-maintenance artifacts are unavailable. Run "
    "notebooks/predictive-maintenance/01_pdm_build.ipynb or npm run prepare:pdm. "
)


def create_app(
    artifact_dir: Path | str | None = None,
    runtime: MaintenanceRuntime | None = None,
) -> FastAPI:
    app_settings = Settings(artifact_dir=artifact_dir) if artifact_dir else settings
    load_error: str | None = None
    if runtime is None:
        try:
            runtime = MaintenanceRuntime(app_settings.artifact_dir)
        except Exception as error:
            load_error = str(error)

    application = FastAPI(title="Compressor Predictive Maintenance API", version="0.1.0")
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

    def require_runtime(request: Request) -> MaintenanceRuntime:
        current: MaintenanceRuntime | None = request.app.state.runtime
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(UNAVAILABLE + (request.app.state.load_error or "")).strip(),
            )
        return current

    @application.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        current: MaintenanceRuntime | None = request.app.state.runtime
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(UNAVAILABLE + (request.app.state.load_error or "")).strip(),
            )
        return HealthResponse(
            status="ok",
            service=app_settings.service_name,
            model="loaded",
            model_version=current.model_version,
            policy_version=str(current.policy["policy_version"]),
            packaged_windows=len(current.manifest),
            scored_hours=len(current.score),
            artifacts=current.artifact_readiness(),
        )

    @application.get("/api/maintenance/model", response_model=ModelInfo)
    def model_info(current: MaintenanceRuntime = Depends(require_runtime)) -> ModelInfo:
        return current.model_info()

    @application.get("/api/maintenance/samples", response_model=list[SampleWindow])
    def samples(
        limit: int = Query(default=8, ge=1, le=24),
        current: MaintenanceRuntime = Depends(require_runtime),
    ) -> list[SampleWindow]:
        return current.samples(max(1, min(limit, 24)))

    @application.post("/api/maintenance/score", response_model=ScoreResponse)
    def score(
        payload: ScoreRequest,
        current: MaintenanceRuntime = Depends(require_runtime),
    ) -> ScoreResponse:
        try:
            return current.score_window(payload)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    @application.get("/api/maintenance/queue", response_model=QueueResponse)
    def queue(
        threshold: float | None = Query(default=None, ge=0, le=20),
        current: MaintenanceRuntime = Depends(require_runtime),
    ) -> QueueResponse:
        return current.queue(threshold)

    return application


app = create_app()
