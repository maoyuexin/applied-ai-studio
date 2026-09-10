from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .config import MAX_PACKAGED_CUSTOMERS, Settings, settings
from .runtime import RecommendRuntime
from .schemas import (
    CompareResponse,
    HealthResponse,
    ModelInfo,
    PackagedCustomer,
    SlotsRequest,
    SlotsResponse,
)

UNAVAILABLE = (
    "Product recommendation artifacts are unavailable. Run the product-recommendations "
    "notebook or npm run prepare:recommendations."
)


def create_app(
    artifact_dir: Path | str | None = None,
    runtime: RecommendRuntime | None = None,
) -> FastAPI:
    app_settings = Settings(artifact_dir=artifact_dir) if artifact_dir else settings
    load_error: str | None = None
    if runtime is None:
        try:
            runtime = RecommendRuntime(app_settings.artifact_dir)
        except Exception as error:
            load_error = str(error)

    application = FastAPI(title="Product Recommendation API", version="0.1.0")
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

    def require_runtime(request: Request) -> RecommendRuntime:
        current: RecommendRuntime | None = request.app.state.runtime
        if current is None:
            raise unavailable(request)
        return current

    def require_customer(current: RecommendRuntime, customer_id: int) -> None:
        if current.is_known_customer(customer_id):
            return
        packaged = ", ".join(str(value) for value in current.packaged_ids())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Customer {customer_id} is not in this retailer's history. The packaged "
                f"demo customers are: {packaged}."
            ),
        )

    @application.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        current: RecommendRuntime | None = request.app.state.runtime
        if current is None:
            raise unavailable(request)
        return HealthResponse(
            status="ok",
            service=app_settings.service_name,
            model="loaded",
            model_version=current.model_version,
            deployed_model=current.policy["ranking_model"],
            packaged_customers=len(current.packaged),
            catalog_products=int(len(current.catalog)),
            matrix_customers=int(current.split.n_users),
            slots=int(current.policy["slots"]),
            artifacts=current.artifact_readiness(),
        )

    @application.get("/api/recommend/model", response_model=ModelInfo)
    def model_info(current: RecommendRuntime = Depends(require_runtime)) -> ModelInfo:
        return current.model_info()

    @application.get("/api/recommend/customers", response_model=list[PackagedCustomer])
    def customers(
        limit: int = Query(default=12, ge=1, le=MAX_PACKAGED_CUSTOMERS),
        current: RecommendRuntime = Depends(require_runtime),
    ) -> list[PackagedCustomer]:
        return current.customers(max(1, min(limit, MAX_PACKAGED_CUSTOMERS)))

    @application.post("/api/recommend/slots", response_model=SlotsResponse)
    def slots(
        payload: SlotsRequest,
        current: RecommendRuntime = Depends(require_runtime),
    ) -> SlotsResponse:
        require_customer(current, payload.customer_id)
        return current.slots(payload.customer_id, payload.protocol)

    @application.get("/api/recommend/compare", response_model=CompareResponse)
    def compare(
        customer_id: int = Query(ge=0),
        current: RecommendRuntime = Depends(require_runtime),
    ) -> CompareResponse:
        require_customer(current, customer_id)
        return current.compare(customer_id)

    return application


app = create_app()
