"""Blender handlers for the video sequencer: image strips, sound, and video output."""

import os
import re

import bpy
from .. import dispatcher

# Refuse to load more images than this into one strip
MAX_SEQUENCE_IMAGES = 100000

# Container -> video codec Blender should encode with
CONTAINER_VIDEO_CODECS = {"MPEG4": "H264", "MKV": "H264", "WEBM": "WEBM"}

# A numbered frame: prefix, digits, extension
_NUMBERED = re.compile(r"^(.*?)(\d+)(\.[^.]+)$")


def _editor():
    """Return the scene's sequence editor, creating it on first use.

    The strip timing names used here (left_handle, content_start and the
    rest) arrived in Blender 5.1, replacing names that are now deprecated.
    """
    scene = bpy.context.scene
    editor = scene.sequence_editor or scene.sequence_editor_create()
    if not hasattr(editor, "strips"):
        raise ValueError("The sequencer tools need Blender 5.1 or later")
    return editor


def _get_strip(name):
    """Get a strip by name, raising if not found."""
    strip = _editor().strips.get(name)
    if strip is None:
        raise ValueError(f"Strip '{name}' not found")
    return strip


def _describe(strip):
    """Summarise a strip as plain data."""
    return {
        "name": strip.name,
        "type": strip.type,
        "channel": strip.channel,
        "frame_start": strip.left_handle,
        # right_handle is the first frame the strip no longer covers
        "frame_end": strip.right_handle - 1,
    }


def _sequence_files(first_frame):
    """List the numbered siblings of first_frame, in numeric order.

    Only files in the same folder with the same prefix and extension count,
    and only those numbered at or after the first frame.
    """
    directory, filename = os.path.split(first_frame)
    match = _NUMBERED.match(filename)
    if match is None:
        return directory, [filename]

    prefix, digits, extension = match.groups()
    first_number = int(digits)
    numbered = []
    for entry in os.listdir(directory):
        other = _NUMBERED.match(entry)
        if other is None:
            continue
        if other.group(1) != prefix or other.group(3).lower() != extension.lower():
            continue
        number = int(other.group(2))
        if number >= first_number:
            numbered.append((number, entry))
    numbered.sort()
    if len(numbered) > MAX_SEQUENCE_IMAGES:
        raise ValueError(
            f"Sequence has {len(numbered)} images; the limit is {MAX_SEQUENCE_IMAGES}"
        )
    return directory, [entry for _, entry in numbered]


def handle_add_image_sequence_strip(params):
    """Add a numbered image sequence to the sequencer as one strip."""
    first_frame = params["first_frame"]
    channel = params.get("channel", 1)
    frame_start = params.get("frame_start", 1)

    if not os.path.isfile(first_frame):
        raise ValueError(f"Image not found: {first_frame}")
    directory, files = _sequence_files(first_frame)
    name = params.get("name") or os.path.splitext(files[0])[0]

    strip = _editor().strips.new_image(
        name, os.path.join(directory, files[0]), channel, frame_start
    )
    for filename in files[1:]:
        strip.elements.append(filename)

    result = _describe(strip)
    result["images"] = len(files)
    return result


def handle_add_sound_strip(params):
    """Add an audio file to the sequencer as a sound strip."""
    filepath = params["filepath"]
    channel = params.get("channel", 2)
    frame_start = params.get("frame_start", 1)
    start_offset = params.get("start_offset", 0.0)
    volume = params.get("volume", 1.0)

    if not os.path.isfile(filepath):
        raise ValueError(f"Sound file not found: {filepath}")
    name = params.get("name") or os.path.splitext(os.path.basename(filepath))[0]

    strip = _editor().strips.new_sound(name, filepath, channel, frame_start)
    if start_offset:
        render = bpy.context.scene.render
        offset_frames = start_offset * render.fps / render.fps_base
        # Slide the strip left and trim the same amount off its head, so the
        # audible part still begins on frame_start.
        strip.content_start = frame_start - offset_frames
        strip.left_handle_offset = offset_frames
    strip.volume = volume

    result = _describe(strip)
    result["volume"] = strip.volume
    return result


def handle_list_strips(params):
    """List every strip in the sequencer."""
    editor = bpy.context.scene.sequence_editor
    if editor is None:
        return []
    return [_describe(strip) for strip in editor.strips]


def handle_remove_strip(params):
    """Remove a strip from the sequencer by name."""
    strip = _get_strip(params["strip_name"])
    name = strip.name
    _editor().strips.remove(strip)
    return {"removed": name}


def handle_render_video(params):
    """Render the frame range to one video file, with sound."""
    filepath = params["filepath"]
    container = params.get("container", "MPEG4")
    quality = params.get("quality", "HIGH")
    audio_codec = params.get("audio_codec", "AAC")

    if container not in CONTAINER_VIDEO_CODECS:
        raise ValueError(f"Unsupported container '{container}'")

    scene = bpy.context.scene
    render = scene.render
    settings = render.image_settings
    ffmpeg = render.ffmpeg

    # Blender 5.x splits image and video output behind media_type
    has_media_type = hasattr(settings, "media_type")
    original = {
        "filepath": render.filepath,
        "media_type": settings.media_type if has_media_type else None,
        "file_format": settings.file_format,
        "format": ffmpeg.format,
        "codec": ffmpeg.codec,
        "constant_rate_factor": ffmpeg.constant_rate_factor,
        "audio_codec": ffmpeg.audio_codec,
    }

    try:
        if has_media_type:
            settings.media_type = "VIDEO"
        settings.file_format = "FFMPEG"
        ffmpeg.format = container
        ffmpeg.codec = CONTAINER_VIDEO_CODECS[container]
        ffmpeg.constant_rate_factor = quality
        ffmpeg.audio_codec = audio_codec
        render.filepath = filepath
        bpy.ops.render.render(animation=True)
    finally:
        render.filepath = original["filepath"]
        ffmpeg.format = original["format"]
        ffmpeg.codec = original["codec"]
        ffmpeg.constant_rate_factor = original["constant_rate_factor"]
        ffmpeg.audio_codec = original["audio_codec"]
        if has_media_type:
            settings.media_type = original["media_type"]
        settings.file_format = original["file_format"]

    return {
        "filepath": filepath,
        "container": container,
        "audio_codec": audio_codec,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "fps": render.fps / render.fps_base,
        "rendered": True,
    }


STRIP_SETTING_TYPES = {"BOOLEAN", "INT", "FLOAT", "ENUM", "STRING"}
STRIP_TRANSFORM_KEYS = {"offset_x", "offset_y", "scale_x", "scale_y", "rotation"}
STRIP_CROP_KEYS = {"min_x", "max_x", "min_y", "max_y"}


def handle_add_sequencer_strip(params):
    editor = _editor()
    kind = params.get("kind")
    channel, start = int(params.get("channel", 1)), int(params.get("frame_start", 1))
    if kind in ("TEXT", "COLOR"):
        strip = editor.strips.new_effect(name=params.get("name", kind.capitalize()), type=kind,
                                         channel=channel, frame_start=start,
                                         length=int(params.get("length", 25)))
        if kind == "TEXT":
            strip.text = params["text"]
            strip.font_size = float(params.get("font_size", 60.0))
        if "color" in params:
            strip.color = params["color"]
    elif kind == "MOVIE":
        path = params["filepath"]
        strip = editor.strips.new_movie(name=params.get("name", os.path.basename(path)),
                                        filepath=path, channel=channel, frame_start=start)
    else:
        raise ValueError(f"Unknown strip kind {kind!r}")
    return _describe(strip)


def handle_set_strip_property(params):
    strip = _get_strip(params["strip_name"])
    props = strip.bl_rna.properties
    for key, value in (params.get("settings") or {}).items():
        rna = props.get(key)
        if rna is None or rna.is_readonly or rna.type not in STRIP_SETTING_TYPES \
                or getattr(rna, "is_array", False) or key == "name":
            settable = sorted(k for k, p in props.items() if not p.is_readonly
                              and p.type in STRIP_SETTING_TYPES
                              and not getattr(p, "is_array", False) and k != "name")
            raise ValueError(f"'{key}' is not a {strip.type.lower()} strip setting. "
                             f"Settings: {', '.join(settable)}")
        try:
            setattr(strip, key, value)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Cannot set {key} to {value!r}: {e}") from None
    for group, keys in (("transform", STRIP_TRANSFORM_KEYS), ("crop", STRIP_CROP_KEYS)):
        for key, value in (params.get(group) or {}).items():
            if key not in keys:
                raise ValueError(f"{group} has no {key!r}")
            target = getattr(strip, group)
            setattr(target, key, int(value) if group == "crop" else float(value))
    return _describe(strip)


def handle_add_strip_fade(params):
    """Key opacity (volume for sound) from 0 up at the start and down to 0 at the end."""
    strip = _get_strip(params["strip_name"])
    prop = "volume" if strip.type == "SOUND" else "blend_alpha"
    full = getattr(strip, prop)
    first, last = strip.left_handle, strip.right_handle - 1
    keyed = []
    fade_in, fade_out = int(params.get("fade_in", 0)), int(params.get("fade_out", 0))
    if fade_in + fade_out > last - first + 1:
        raise ValueError(f"The fades ({fade_in}+{fade_out} frames) are longer than the "
                         f"strip ({last - first + 1} frames)")
    keys = []
    if fade_in:
        keys += [(first, 0.0), (first + fade_in, full)]
    if fade_out:
        keys += [(last - fade_out, full), (last, 0.0)]
    for frame, value in keys:
        setattr(strip, prop, value)
        strip.keyframe_insert(prop, frame=frame)
        keyed.append(frame)
    setattr(strip, prop, full)
    return {"strip": strip.name, "property": prop, "keyed_frames": keyed}


def register():
    """Register sequencer handlers with the dispatcher."""
    dispatcher.register_handler("add_image_sequence_strip", handle_add_image_sequence_strip)
    dispatcher.register_handler("add_sound_strip", handle_add_sound_strip)
    dispatcher.register_handler("add_sequencer_strip", handle_add_sequencer_strip)
    dispatcher.register_handler("set_strip_property", handle_set_strip_property)
    dispatcher.register_handler("add_strip_fade", handle_add_strip_fade)
    dispatcher.register_handler("list_strips", handle_list_strips)
    dispatcher.register_handler("remove_strip", handle_remove_strip)
    dispatcher.register_handler("render_video", handle_render_video)
