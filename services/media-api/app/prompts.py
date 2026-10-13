from .schemas import ImageOptions, ShotId


CAR_DESCRIPTION = (
    "SOLENNE GT is a fictional, unbranded electric luxury grand tourer: two doors, long hood, "
    "low roofline, champagne-silver surfaces, slim horizon headlamps, flush glass, elegant cabin, "
    "no real-world badge, no real trademark, no recognizable trade dress."
)

SHOT_PROMPTS: dict[ShotId, dict[str, str]] = {
    "s1": {
        "title": "Studio reveal",
        "picture": "Dark studio; a thin light sweeps across the hood and silent badge.",
        "sound": "low synth swell",
    },
    "s2": {
        "title": "Coastal glide",
        "picture": "Wet coastal highway at blue hour with city light reflections on the hood.",
        "sound": "soft tire hiss and a deep electric tone",
    },
    "s3": {
        "title": "Interior craft",
        "picture": "Close detail on stitched leather, glass dashboard and warm ambient light.",
        "sound": "quiet tactile clicks",
    },
    "s4": {
        "title": "Arrival pause",
        "picture": "Hotel canopy arrival; reflections hold on the shoulder line and wheel arch.",
        "sound": "city room tone, no engine roar",
    },
    "s5": {
        "title": "End card",
        "picture": "Clean profile composition with room for the visible AI label and fictional brand.",
        "sound": "one clean chime",
    },
}


def build_image_prompt(
    shot_id: ShotId,
    options: ImageOptions,
    free_text: str | None,
    max_characters: int,
    *,
    edit: bool = False,
) -> str:
    shot = SHOT_PROMPTS[shot_id]
    parts = [
        "Create a photorealistic advertising still for a classroom-only fictional luxury car campaign.",
        f"Vehicle: {CAR_DESCRIPTION}",
        f"Shot: {shot['title']} — {shot['picture']}",
        f"Paint color: {options.paint}. Lighting: {options.lighting}. Wheels: {options.wheels}. Setting: {options.setting}.",
        "Keep the same fictional car identity, readable but fictional badging, plausible reflections, correct wheel geometry, and no real brand marks.",
        "Composition should be 16:9, premium automotive advertising, projector-readable, cinematic but not cluttered.",
    ]
    if edit:
        parts.append("Edit the supplied image while preserving the car identity and camera continuity.")
    if free_text:
        parts.append(f"Short instructor-approved direction: {free_text}")
    return _truncate_prompt(" ".join(parts), max_characters)


def build_video_prompt(shot_id: ShotId, free_text: str | None, max_characters: int) -> str:
    shot = SHOT_PROMPTS[shot_id]
    parts = [
        "Create one 4-second 1280x720 Sora take for a classroom-only fictional luxury car ad.",
        f"Vehicle: {CAR_DESCRIPTION}",
        f"Picture: {shot['picture']}",
        f"Sound direction: {shot['sound']}.",
        "Keep motion restrained and premium. Do not include real brand marks, real logos, license plates, or readable legal claims.",
    ]
    if free_text:
        parts.append(f"Short instructor-approved direction: {free_text}")
    return _truncate_prompt(" ".join(parts), max_characters)


def _truncate_prompt(prompt: str, max_characters: int) -> str:
    if len(prompt) <= max_characters:
        return prompt
    return prompt[: max_characters - 3].rstrip() + "..."
