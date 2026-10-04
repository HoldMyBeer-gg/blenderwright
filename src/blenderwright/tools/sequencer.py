"""MCP tools for Blender's video sequencer: image strips, sound, and video output."""

from typing import Any

from blenderwright.connection import BlenderConnection
from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_object_name,
    validate_new_name,
    validate_enum,
    validate_numeric_range,
    validate_file_path,
    validate_output_path,
    default_output_path,
    ValidationError,
)

# Blender's sequencer has 128 channels
MAX_SEQUENCER_CHANNEL = 128

# Largest frame number Blender accepts
MAX_FRAME = 1048574

# Sound strip volume is a multiplier; Blender caps it at 100
MAX_STRIP_VOLUME = 100.0

# Image formats an image strip can load
ALLOWED_STRIP_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".exr", ".tiff", ".tif", ".bmp", ".webp",
}

# Audio formats a sound strip can load
ALLOWED_SOUND_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus"}

# Video containers, each with the file extension it is written under
VIDEO_CONTAINER_EXTENSIONS = {"MPEG4": ".mp4", "MKV": ".mkv", "WEBM": ".webm"}
ALLOWED_VIDEO_CONTAINERS = set(VIDEO_CONTAINER_EXTENSIONS)

# Constant rate factor presets, lowest to highest quality
ALLOWED_VIDEO_QUALITIES = {
    "LOWEST", "VERYLOW", "LOW", "MEDIUM", "HIGH", "PERC_LOSSLESS", "LOSSLESS",
}

ALLOWED_AUDIO_CODECS = {"NONE", "AAC", "MP3", "OPUS"}

# WebM only carries Opus (or Vorbis) audio
WEBM_AUDIO_CODECS = {"NONE", "OPUS"}


def _send(command: str, params: dict[str, Any] | None = None, **send_options: Any) -> Any:
    """Send a sequencer command and handle errors."""
    conn = get_connection()
    response = conn.send_command(command, params, **send_options)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")


@mcp.tool()
def add_image_sequence_strip(
    first_frame: str,
    name: str = "",
    channel: int = 1,
    frame_start: int = 1,
) -> dict[str, Any]:
    """Add rendered frames to the sequencer as one image strip.

    Give the first frame of a numbered sequence, such as the output of
    render_animation. Every file in the same folder that shares its prefix and
    extension is added in numeric order, one image per timeline frame.

    Args:
        first_frame: Path to the first image, e.g. /renders/f_0001.png.
        name: Optional name for the strip.
        channel: Sequencer channel, 1-128. Higher channels draw on top.
        frame_start: Timeline frame where the strip begins.

    Returns:
        Dict with the strip name, image count, and the frames it covers.
    """
    first_frame = validate_file_path(
        first_frame, allowed_extensions=ALLOWED_STRIP_IMAGE_EXTENSIONS, must_exist=True
    )
    if name:
        name = validate_new_name(name)
    channel = validate_numeric_range(
        channel, min_val=1, max_val=MAX_SEQUENCER_CHANNEL, name="channel"
    )
    frame_start = validate_numeric_range(
        frame_start, min_val=-MAX_FRAME, max_val=MAX_FRAME, name="frame_start"
    )

    return _send("add_image_sequence_strip", {
        "first_frame": first_frame,
        "name": name,
        "channel": int(channel),
        "frame_start": int(frame_start),
    })


@mcp.tool()
def add_sound_strip(
    filepath: str,
    name: str = "",
    channel: int = 2,
    frame_start: int = 1,
    start_offset: float = 0.0,
    volume: float = 1.0,
) -> dict[str, Any]:
    """Add an audio file to the sequencer as a sound strip.

    Args:
        filepath: Path to the audio file (.wav, .mp3, .flac, .ogg,
            .m4a, .aac, .opus).
        name: Optional name for the strip.
        channel: Sequencer channel, 1-128.
        frame_start: Timeline frame where the sound becomes audible.
        start_offset: Seconds to skip at the start of the audio file, so a
            clip can begin partway in.
        volume: Volume multiplier, 0-100. 1.0 leaves the audio unchanged.

    Returns:
        Dict with the strip name and the frames it covers.
    """
    filepath = validate_file_path(
        filepath, allowed_extensions=ALLOWED_SOUND_EXTENSIONS, must_exist=True
    )
    if name:
        name = validate_new_name(name)
    channel = validate_numeric_range(
        channel, min_val=1, max_val=MAX_SEQUENCER_CHANNEL, name="channel"
    )
    frame_start = validate_numeric_range(
        frame_start, min_val=-MAX_FRAME, max_val=MAX_FRAME, name="frame_start"
    )
    start_offset = validate_numeric_range(
        start_offset, min_val=0.0, max_val=86400.0, name="start_offset"
    )
    volume = validate_numeric_range(
        volume, min_val=0.0, max_val=MAX_STRIP_VOLUME, name="volume"
    )

    return _send("add_sound_strip", {
        "filepath": filepath,
        "name": name,
        "channel": int(channel),
        "frame_start": int(frame_start),
        "start_offset": float(start_offset),
        "volume": float(volume),
    })


@mcp.tool()
def list_strips() -> list[dict[str, Any]]:
    """List every strip in the sequencer.

    Returns:
        List of dicts with name, type, channel, and first and last frame.
    """
    return _send("list_strips")


@mcp.tool()
def remove_strip(strip_name: str) -> dict[str, Any]:
    """Remove a strip from the sequencer by name.

    Args:
        strip_name: Name of the strip to remove.

    Returns:
        Confirmation dict.
    """
    strip_name = validate_object_name(strip_name)
    return _send("remove_strip", {"strip_name": strip_name})


@mcp.tool()
def render_video(
    filepath: str = "",
    container: str = "MPEG4",
    quality: str = "HIGH",
    audio_codec: str = "AAC",
) -> dict[str, Any]:
    """Render the scene's frame range to a single video file, with sound.

    Sequencer strips are used when there are any, so frames already rendered
    with render_animation can be assembled with a sound strip in seconds.
    With an empty sequencer the 3D scene is rendered. Playback speed follows
    the scene fps.

    Args:
        filepath: Output path, in a directory that exists. Empty means the
            system temp directory. The extension must match the
            container: .mp4 for MPEG4, .mkv for MKV, .webm for WEBM.
        container: Video container. One of: MPEG4, MKV, WEBM.
        quality: Encoder quality preset, from LOWEST to LOSSLESS.
        audio_codec: Audio codec, or NONE for a silent video. WEBM accepts
            only OPUS or NONE.

    Returns:
        Dict with the output path, frame range, and fps.
    """
    validate_enum(container, ALLOWED_VIDEO_CONTAINERS, name="container")
    validate_enum(quality, ALLOWED_VIDEO_QUALITIES, name="quality")
    validate_enum(audio_codec, ALLOWED_AUDIO_CODECS, name="audio_codec")
    if container == "WEBM" and audio_codec not in WEBM_AUDIO_CODECS:
        raise ValidationError(
            f"WEBM cannot carry {audio_codec} audio. Use OPUS or NONE."
        )
    # Resolved to an absolute path here: Blender would resolve a relative one
    # against the .blend, somewhere the caller never named.
    extension = VIDEO_CONTAINER_EXTENSIONS[container]
    filepath = validate_output_path(filepath or default_output_path(f"render{extension}"),
                                    allowed_extensions={extension})

    return _send("render_video", {
        "filepath": filepath,
        "container": container,
        "quality": quality,
        "audio_codec": audio_codec,
    }, timeout=BlenderConnection.ANIMATION_TIMEOUT)
