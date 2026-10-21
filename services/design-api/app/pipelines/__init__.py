from ..config import Settings
from .article import ArticlePipeline
from .base import Pipeline
from .image import ImagePipeline
from .inspect import InspectPipeline
from .video import VideoPipeline
from .voice import VoicePipeline


def build_pipelines(settings: Settings) -> dict[str, Pipeline]:
    pipelines: list[Pipeline] = [
        VideoPipeline(poll_seconds=settings.video_poll_seconds, timeout_seconds=settings.video_timeout_seconds),
        ImagePipeline(),
        VoicePipeline(),
        ArticlePipeline(),
        InspectPipeline(),
    ]
    return {pipeline.key: pipeline for pipeline in pipelines}
