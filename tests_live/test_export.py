"""Exporter options in a real Blender: they reach the operator and change the file."""

import pytest

from blenderwright.tools.file_ops import export_file
from blenderwright.tools.objects import create_object
from blenderwright.tools.modeling import add_modifier, apply_modifier


@pytest.fixture
def dense(scene):
    create_object("UV_SPHERE", name="Ball")
    add_modifier("Ball", "SUBSURF", name="Smooth")
    apply_modifier("Ball", "Smooth")
    return scene


def test_draco_makes_the_file_smaller(dense):
    plain, packed = dense / "plain.glb", dense / "packed.glb"
    export_file(str(plain))
    export_file(str(packed), options={"export_draco_mesh_compression_enable": True,
                                      "export_draco_mesh_compression_level": 6})
    assert packed.stat().st_size < plain.stat().st_size * 0.6


def test_unknown_option_lists_the_real_ones(dense):
    with pytest.raises(RuntimeError, match="export_apply"):
        export_file(str(dense / "a.glb"), options={"export_dracoo": True})


@pytest.mark.parametrize("option", ["filepath", "export_texture_dir", "filter_glob"])
def test_text_settings_are_refused(dense, option):
    with pytest.raises(RuntimeError, match="text"):
        export_file(str(dense / "a.glb"), options={option: "x"})


def test_obj_option(dense):
    path = dense / "tri.obj"
    export_file(str(path), options={"export_triangulated_mesh": True})
    faces = [line for line in path.read_text().splitlines() if line.startswith("f ")]
    assert faces and all(len(line.split()) == 4 for line in faces)  # every face a triangle
