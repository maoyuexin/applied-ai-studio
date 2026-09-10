from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, settings
from .runtime import ForecastRuntime
from .schemas import (
    MAX_RATIO,
    MIN_RATIO,
    HealthResponse,
    ModelInfo,
    PlanRequest,
    PlanResponse,
    PolicySweepResponse,
    ProductSummary,
)

UNAVAILABLE = (
    "Demand-forecasting artifacts are unavailable. Run "
    "notebooks/demand-forecasting/01_forecast_build.ipynb or npm run prepare:forecast. "
)


def create_app(
    artifact_dir: Path | str | None = None,
    runtime: ForecastRuntime | None = None,
) -> FastAPI:
    app_settings = Settings(artifact_dir=artifact_dir) if artifact_dir else settings
    load_error: str | None = None
    if runtime is None:
        try:
            runtime = ForecastRuntime(app_settings.artifact_dir)
        except Exception as error:
            load_error = str(error)

    application = FastAPI(title="Weekly Demand Forecast API", version="0.1.0")
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

    def require_runtime(request: Request) -> ForecastRuntime:
        current: ForecastRuntime | None = request.app.state.runtime
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(UNAVAILABLE + (request.app.state.load_error or "")).strip(),
            )
        return current

    @application.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        current: ForecastRuntime | None = request.app.state.runtime
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
            policy_version=current.policy_version,
            packaged_products=len(current.manifest),
            cohort_products=len(current.codes),
            scored_product_weeks=len(current.scored),
            artifacts=current.artifact_readiness(),
        )

    @application.get("/api/forecast/model", response_model=ModelInfo)
    def model_info(current: ForecastRuntime = Depends(require_runtime)) -> ModelInfo:
        return current.model_info()

    @application.get("/api/forecast/products", response_model=list[ProductSummary])
    def products(
        limit: int = Query(default=10, ge=1, le=24),
        current: ForecastRuntime = Depends(require_runtime),
    ) -> list[ProductSummary]:
        return current.products(max(1, min(limit, 24)))

    @application.post("/api/forecast/plan", response_model=PlanResponse)
    def plan(
        payload: PlanRequest,
        current: ForecastRuntime = Depends(require_runtime),
    ) -> PlanResponse:
        try:
            return current.plan(payload)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    @application.get("/api/forecast/policy-sweep", response_model=PolicySweepResponse)
    def policy_sweep(
        ratio: float | None = Query(default=None, ge=MIN_RATIO, le=MAX_RATIO),
        current: ForecastRuntime = Depends(require_runtime),
    ) -> PolicySweepResponse:
        return current.policy_sweep(ratio)

    return application


app = create_app()
