import base64
from datetime import date
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .clients import FoundryImageClient, MediaProviderError, SoraVideoClient
from .config import Settings, settings
from .prompts import build_image_prompt, build_video_prompt
from .schemas import (
    HealthResponse,
    ImageEditRequest,
    ImageGenerateRequest,
    ImageResponse,
    QuotaView,
    StatusResponse,
    VideoCreateRequest,
    VideoJobResponse,
)


class DailyQuota:
    def __init__(self, image_cap: int, video_cap: int) -> None:
        self.image_cap = image_cap
        self.video_cap = video_cap
        self.day = date.today()
        self.images_used = 0
        self.videos_used = 0

    def remaining(self) -> QuotaView:
        self._rollover()
        return QuotaView(
            images=max(self.image_cap - self.images_used, 0),
            videos=max(self.video_cap - self.videos_used, 0),
        )

    def reserve_image(self) -> QuotaView:
        self._rollover()
        if self.images_used >= self.image_cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily live image quota is exhausted. Use recorded mode.",
            )
        self.images_used += 1
        return self.remaining()

    def reserve_video(self) -> QuotaView:
        self._rollover()
        if self.videos_used >= self.video_cap:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily live video quota is exhausted. Use recorded mode.",
            )
        self.videos_used += 1
        return self.remaining()

    def _rollover(self) -> None:
        today = date.today()
        if today != self.day:
            self.day = today
            self.images_used = 0
            self.videos_used = 0


def create_app(
    app_settings: Settings | None = None,
    *,
    image_client: Any | None = None,
    video_client: Any | None = None,
) -> FastAPI:
    current_settings = app_settings or settings
    if current_settings.image_pixels > 2_359_296:
        raise ValueError("MAI image width * height must be <= 2,359,296 pixels.")

    application = FastAPI(title="Promo Studio Media API", version="0.1.0")
    application.state.settings = current_settings
    application.state.quota = DailyQuota(
        current_settings.daily_image_cap,
        current_settings.daily_video_cap,
    )
    application.state.image_client = image_client or FoundryImageClient(current_settings)
    application.state.video_client = video_client or SoraVideoClient(current_settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=current_settings.origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @application.get("/health", response_model=HealthResponse)
    def health(request: Request) -> HealthResponse:
        app_settings = _settings(request)
        return HealthResponse(
            status="ok",
            service=app_settings.service_name,
            live_images=app_settings.live_images,
            live_video=app_settings.live_video,
        )

    @application.get("/api/media/status", response_model=StatusResponse)
    def media_status(request: Request) -> StatusResponse:
        app_settings = _settings(request)
        quota = _quota(request)
        return StatusResponse(
            service=app_settings.service_name,
            live_images=app_settings.live_images,
            live_video=app_settings.live_video,
            remaining_daily_quota=quota.remaining(),
            caps=QuotaView(images=app_settings.daily_image_cap, videos=app_settings.daily_video_cap),
            image_model=app_settings.image_deployment,
            video_model=app_settings.video_model,
            note="Live generation is off unless MEDIA_LIVE_IMAGES=1 or MEDIA_LIVE_VIDEO=1.",
        )

    @application.post("/api/media/images/generate", response_model=ImageResponse)
    async def generate_image(payload: ImageGenerateRequest, request: Request) -> ImageResponse:
        app_settings = _settings(request)
        _require_live(app_settings.live_images, "Live image generation is disabled.")
        remaining = _quota(request).reserve_image()
        prompt = build_image_prompt(
            payload.shot_id,
            payload.options,
            payload.free_text,
            app_settings.max_prompt_characters,
        )
        started = perf_counter()
        try:
            image_b64 = await request.app.state.image_client.generate(prompt)
        except MediaProviderError as error:
            raise _provider_http_exception(error) from error
        return ImageResponse(
            image_data_url=f"data:image/png;base64,{image_b64}",
            elapsed_seconds=round(perf_counter() - started, 3),
            prompt_summary=prompt,
            remaining_daily_quota=remaining,
        )

    @application.post("/api/media/images/edit", response_model=ImageResponse)
    async def edit_image(payload: ImageEditRequest, request: Request) -> ImageResponse:
        app_settings = _settings(request)
        _require_live(app_settings.live_images, "Live image editing is disabled.")
        remaining = _quota(request).reserve_image()
        prompt = build_image_prompt(
            payload.shot_id,
            payload.options,
            payload.free_text,
            app_settings.max_prompt_characters,
            edit=True,
        )
        started = perf_counter()
        try:
            image_b64 = await request.app.state.image_client.edit(prompt, payload.image_b64)
        except MediaProviderError as error:
            raise _provider_http_exception(error) from error
        return ImageResponse(
            image_data_url=f"data:image/png;base64,{image_b64}",
            elapsed_seconds=round(perf_counter() - started, 3),
            prompt_summary=prompt,
            remaining_daily_quota=remaining,
        )

    @application.post("/api/media/videos", response_model=VideoJobResponse)
    async def create_video(payload: VideoCreateRequest, request: Request) -> VideoJobResponse:
        app_settings = _settings(request)
        _require_live(app_settings.live_video, "Live video generation is disabled.")
        remaining = _quota(request).reserve_video()
        prompt = build_video_prompt(
            payload.shot_id,
            payload.free_text,
            app_settings.max_prompt_characters,
        )
        try:
            job = await request.app.state.video_client.create(prompt, payload.input_reference_b64)
        except MediaProviderError as error:
            raise _provider_http_exception(error) from error
        return _video_job(job, prompt_summary=prompt, remaining=remaining)

    @application.get("/api/media/videos/{video_id}", response_model=VideoJobResponse)
    async def get_video(video_id: str, request: Request) -> VideoJobResponse:
        app_settings = _settings(request)
        _require_live(app_settings.live_video, "Live video generation is disabled.")
        try:
            job = await request.app.state.video_client.get(video_id)
            response = _video_job(job)
            if response.status == "completed":
                content = await request.app.state.video_client.download(video_id)
                response.video_data_url = f"data:video/mp4;base64,{base64.b64encode(content).decode('ascii')}"
            return response
        except MediaProviderError as error:
            raise _provider_http_exception(error) from error

    return application


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _quota(request: Request) -> DailyQuota:
    return request.app.state.quota


def _require_live(enabled: bool, message: str) -> None:
    if not enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=message)


def _provider_http_exception(error: MediaProviderError) -> HTTPException:
    if error.content_filter:
        status_code = status.HTTP_409_CONFLICT
    elif error.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=status_code, detail=str(error))


def _video_job(
    payload: dict[str, Any],
    *,
    prompt_summary: str | None = None,
    remaining: QuotaView | None = None,
) -> VideoJobResponse:
    video_id = payload.get("id")
    if not isinstance(video_id, str) or not video_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Video provider response did not include an id.",
        )
    return VideoJobResponse(
        id=video_id,
        status=str(payload.get("status", "unknown")),
        progress=int(payload["progress"]) if isinstance(payload.get("progress"), int) else None,
        prompt_summary=prompt_summary,
        remaining_daily_quota=remaining,
        error=str(payload["error"]) if payload.get("error") else None,
    )


app = create_app()
