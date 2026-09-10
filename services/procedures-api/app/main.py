from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, settings
from .runtime import ProcedureRuntime
from .schemas import (
    AskRequest,
    AskResult,
    CorpusView,
    HealthResponse,
    ModelInfo,
    PackagedQuestion,
)

UNAVAILABLE = (
    "Procedure assistant artifacts are unavailable. Run the procedure-assistant notebook or "
    "npm run prepare:procedures."
)


def create_app(
    artifact_dir: Path | str | None = None,
    runtime: ProcedureRuntime | None = None,
) -> FastAPI:
    app_settings = Settings(artifact_dir=artifact_dir) if artifact_dir else settings
    load_error: str | None = None
    if runtime is None:
        try:
            runtime = ProcedureRuntime(app_settings.artifact_dir)
        except Exception as error:
            load_error = str(error)

    application = FastAPI(title="Grounded Procedure Assistant API", version="0.1.0")
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

    def require_runtime(request: Request) -> ProcedureRuntime:
        current: ProcedureRuntime | None = request.app.state.runtime
        if current is None:
            raise unavailable(request)
        return current

    @application.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        current: ProcedureRuntime | None = request.app.state.runtime
        if current is None:
            raise unavailable(request)
        return HealthResponse(
            status="ok",
            service=app_settings.service_name,
            model="loaded",
            model_version=current.model_version,
            corpus=str(current.manifest["corpus"]),
            embedder=str(current.card["how_it_represents_text"]["embedder"]),
            chunks=int(current.chunks.shape[0]),
            documents_indexed=int(current.chunks["source"].nunique()),
            packaged_questions=len(current.answers),
            refusal_threshold=current.tau,
            artifacts=current.artifact_readiness(),
        )

    @application.get("/api/procedures/model", response_model=ModelInfo)
    def model_info(current: ProcedureRuntime = Depends(require_runtime)) -> ModelInfo:
        return current.model_info()

    @application.get("/api/procedures/questions", response_model=list[PackagedQuestion])
    def questions(
        limit: int = Query(default=20, ge=1, le=24),
        current: ProcedureRuntime = Depends(require_runtime),
    ) -> list[PackagedQuestion]:
        return current.questions(max(1, min(limit, 24)))

    @application.post("/api/procedures/ask", response_model=AskResult)
    def ask(
        payload: AskRequest,
        current: ProcedureRuntime = Depends(require_runtime),
    ) -> AskResult:
        try:
            return current.ask(payload.question)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    @application.get("/api/procedures/corpus", response_model=CorpusView)
    def corpus(current: ProcedureRuntime = Depends(require_runtime)) -> CorpusView:
        return current.corpus_view()

    return application


app = create_app()
