"""MCP tool for baking textures with Cycles: albedo, normal maps, AO and more."""

from typing import Any

from blenderwright.connection import BlenderConnection
from blenderwright.server import mcp, get_connection
from blenderwright.validators import (
    validate_enum,
    validate_int,
    validate_numeric_range,
    validate_object_name,
    validate_output_path,
    ValidationError,
)

# bpy.ops.object.bake type enum in Blender 5.2
ALLOWED_BAKE_TYPES = {
    "COMBINED", "AO", "SHADOW", "POSITION", "NORMAL", "UV", "ROUGHNESS", "EMIT",
    "ENVIRONMENT", "DIFFUSE", "GLOSSY", "TRANSMISSION",
}
ALLOWED_NORMAL_SPACES = {"TANGENT", "OBJECT"}
ALLOWED_BAKE_EXTENSIONS = {".png", ".exr", ".tif", ".tiff", ".jpg", ".jpeg"}


@mcp.tool()
def bake_texture(
    object_name: str,
    bake_type: str,
    filepath: str,
    resolution: int = 1024,
    source_object: str = "",
    cage_extrusion: float = 0.0,
    max_ray_distance: float = 0.0,
    margin: int = 16,
    samples: int = 64,
    diffuse_color_only: bool = True,
    normal_space: str = "TANGENT",
) -> dict[str, Any]:
    """Bake a texture map from an object's materials (or a high-poly source) into an image.

    The object needs UVs (smart_uv_project) and a material. Cycles is used
    for the bake and the render engine is put back afterwards.

    Args:
        object_name: Object whose UVs receive the bake (the low-poly one).
        bake_type: DIFFUSE (base colour, see diffuse_color_only), NORMAL,
            AO, ROUGHNESS, EMIT, COMBINED (fully lit), GLOSSY,
            TRANSMISSION, SHADOW, ENVIRONMENT, POSITION or UV.
        filepath: Image to write: .png, .exr, .tif or .jpg, in an existing
            directory. Use .exr or .png for normal maps.
        resolution: Square image size in pixels, 64 to 8192.
        source_object: High-poly object to bake from onto object_name
            (selected to active). Leave empty to bake the object onto itself.
        cage_extrusion: How far rays start outside the low-poly surface when
            baking from a source, 0.0 to 10.0. Raise it if the bake has holes.
        max_ray_distance: Furthest a ray may travel to hit the source, 0 for
            no limit, up to 10.0.
        margin: Pixels to bleed past UV island edges, 0 to 64, so mipmaps
            don't show seams.
        samples: Cycles samples for the bake, 1 to 4096. AO and COMBINED
            need more; DIFFUSE and NORMAL are clean at 1 to 16.
        diffuse_color_only: For DIFFUSE, bake the flat base colour (albedo)
            rather than lit colour. Game engines want this.
        normal_space: For NORMAL: TANGENT (game engines, normal map nodes)
            or OBJECT.

    Returns:
        Dict with the file written, its size and the image name in Blender.
    """
    params: dict[str, Any] = {
        "object_name": validate_object_name(object_name),
        "bake_type": validate_enum(bake_type, ALLOWED_BAKE_TYPES, name="bake_type"),
        "filepath": validate_output_path(filepath, ALLOWED_BAKE_EXTENSIONS),
        "resolution": validate_int(resolution, 64, 8192, name="resolution"),
        "margin": validate_int(margin, 0, 64, name="margin"),
        "samples": validate_int(samples, 1, 4096, name="samples"),
        "diffuse_color_only": bool(diffuse_color_only),
        "normal_space": validate_enum(normal_space, ALLOWED_NORMAL_SPACES, name="normal_space"),
    }
    if source_object:
        params["source_object"] = validate_object_name(source_object)
        if params["source_object"] == params["object_name"]:
            raise ValidationError("source_object must be a different object to bake from")
        params["cage_extrusion"] = validate_numeric_range(
            cage_extrusion, min_val=0.0, max_val=10.0, name="cage_extrusion")
        params["max_ray_distance"] = validate_numeric_range(
            max_ray_distance, min_val=0.0, max_val=10.0, name="max_ray_distance")
    elif cage_extrusion < 0:
        raise ValidationError("cage_extrusion must be >= 0")

    conn = get_connection()
    response = conn.send_command("bake_texture", params, timeout=BlenderConnection.RENDER_TIMEOUT)
    if response.get("status") == "error":
        raise RuntimeError(f"Blender error: {response.get('result')}")
    return response.get("result")
