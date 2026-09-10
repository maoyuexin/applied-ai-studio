from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, settings
from .runtime import ComplaintRuntime
from .schemas import (
    ClassificationResult,
    ClassifyRequest,
    HealthResponse,
    ModelInfo,
    PackagedComplaint,
    QueueBoard,
)

UNAVAILABLE = (
    "Complaint model artifacts are unavailable. Run the complaint-routing notebook or "
    "npm run prepare:complaints."
)


def create_app(
    artifact_dir: Path | str | None = None,
    runtime: ComplaintRuntime | None = None,
) -> FastAPI:
    app_settings = Settings(artifact_dir=artifact_dir) if artifact_dir else settings
    load_error: str | None = None
    if runtime is None:
        try:
            runtime = ComplaintRuntime(app_settings.artifact_dir)
        except Exception as error:
            load_error = str(error)

    application = FastAPI(title="Consumer-complaint Routing API", version="0.1.0")
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

    def unavailable(request: Request) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{UNAVAILABLE} {request.app.state.load_error or ''}".strip(),
        )

    def require_runtime(request: Request) -> ComplaintRuntime:
        current: ComplaintRuntime | None = request.app.state.runtime
        if current is None:
            raise unavailable(request)
        return current

    @application.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        current: ComplaintRuntime | None = request.app.state.runtime
        if current is None:
            raise unavailable(request)
        return HealthResponse(
            status="ok",
            service=app_settings.service_name,
            model="loaded",
            model_version=current.model_version,
            packaged_complaints=int(len(current.manifest)),
            teams=len(current.teams),
            artifacts=current.artifact_readiness(),
        )

    @application.get("/api/complaints/model", response_model=ModelInfo)
    def model_info(current: ComplaintRuntime = Depends(require_runtime)) -> ModelInfo:
        return current.model_info()

    @application.get("/api/complaints/samples", response_model=list[PackagedComplaint])
    def samples(
        limit: int = Query(default=12, ge=1, le=24),
        current: ComplaintRuntime = Depends(require_runtime),
    ) -> list[PackagedComplaint]:
        return current.samples(max(1, min(limit, 24)))

    @application.post("/api/complaints/classify", response_model=ClassificationResult)
    def classify(
        payload: ClassifyRequest,
        current: ComplaintRuntime = Depends(require_runtime),
    ) -> ClassificationResult:
        try:
            return current.classify(payload.narrative)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    @application.get("/api/complaints/queues", response_model=QueueBoard)
    def queues(
        limit: int = Query(default=60, ge=1, le=60),
        current: ComplaintRuntime = Depends(require_runtime),
    ) -> QueueBoard:
        return current.queues(max(1, min(limit, 60)))

    return application


app = create_app()
