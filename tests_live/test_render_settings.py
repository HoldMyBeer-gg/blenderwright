"""Render and render-settings tools in a real Blender. Replaces the fake-bpy
rendering handler tests; each tool returns the state Blender ended up in."""

import pytest

from blenderwright import server
from blenderwright.tools import rendering as r
from blenderwright.tools import render_settings as rs
from blenderwright.tools.sequencer import render_video


class TestEngineAndOutput:
    @pytest.mark.parametrize("engine", ["BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"])
    def test_every_engine(self, scene, engine):
        assert r.set_render_engine(engine)["engine"] == engine

    def test_old_eevee_next_name_maps_to_eevee(self, scene):
        assert r.set_render_engine("BLENDER_EEVEE_NEXT")["engine"] == "BLENDER_EEVEE"

    def test_resolution_and_samples(self, scene):
        assert r.set_render_resolution(640, 360, 50) == {
            "resolution_x": 640, "resolution_y": 360, "resolution_percentage": 50}
        r.set_render_engine("CYCLES")
        assert r.set_render_samples(16) == {"engine": "CYCLES", "samples": 16}
        r.set_render_engine("BLENDER_EEVEE")
        assert r.set_render_samples(32)["samples"] == 32

    def test_image_output_after_a_video(self, scene):
        """Since 5.0 an image format is refused while the output is video."""
        r.set_render_resolution(32, 32)
        r.set_render_engine("CYCLES")
        r.set_render_samples(1)
        render_video(filepath=str(scene / "clip.mp4"))
        assert r.set_output_format("PNG")["format"] == "PNG"
        out = scene / "still.png"
        r.render_image(filepath=str(out))
        assert out.exists()


class TestColorManagement:
    def test_short_look_gets_the_agx_prefix(self, scene):
        result = rs.set_color_management(view_transform="AgX", look="Punchy")
        assert result["look"] == "AgX - Punchy"

    def test_standard_look_used_as_is(self, scene):
        result = rs.set_color_management(view_transform="Standard", look="High Contrast")
        assert result["look"] == "High Contrast"

    def test_look_follows_the_current_transform(self, scene):
        rs.set_color_management(view_transform="AgX")
        assert rs.set_color_management(look="High Contrast")["look"] == "AgX - High Contrast"

    def test_none_clears(self, scene):
        rs.set_color_management(view_transform="AgX", look="Punchy")
        assert rs.set_color_management(look="None")["look"] == "None"

    def test_wrong_look_for_the_transform(self, scene):
        with pytest.raises(RuntimeError, match="Punchy"):
            rs.set_color_management(view_transform="Standard", look="Punchy")

    def test_white_balance_switches_on(self, scene):
        result = rs.set_color_management(white_balance_temperature=5000.0)
        assert result["use_white_balance"] is True
        assert result["white_balance_temperature"] == pytest.approx(5000.0)


class TestQuality:
    def test_film(self, scene):
        result = rs.set_film(transparent=True, transparent_glass=True, filter_width=1.2)
        assert result["transparent"] is True and result["transparent_glass"] is True
        assert result["filter_width"] == pytest.approx(1.2)

    def test_denoiser_missing_on_this_machine_is_explained(self, scene):
        reply = server.get_connection().send_command("set_denoising", {"denoiser": "NOPE"})
        assert reply["status"] == "error"

    def test_denoising(self, scene):
        assert rs.set_denoising(enabled=True, denoiser="OPENIMAGEDENOISE")["enabled"] is True

    def test_sampling(self, scene):
        result = rs.set_cycles_sampling(adaptive=True, noise_threshold=0.05, min_samples=4)
        assert result["adaptive"] is True and result["min_samples"] == 4
        assert result["noise_threshold"] == pytest.approx(0.05)

    def test_light_paths(self, scene):
        result = rs.set_light_paths(total=4, diffuse=2)
        assert (result["total"], result["diffuse"]) == (4, 2)

    def test_motion_blur(self, scene):
        result = rs.set_motion_blur(enabled=True, shutter=0.8, position="START")
        assert result["enabled"] is True and result["position"] == "START"
        assert result["shutter"] == pytest.approx(0.8)

    def test_passes_land_on_each_owner(self, scene):
        """mist and z live on the view layer, shadow_catcher on its Cycles
        settings, transparent on its EEVEE settings: a wrong owner errors."""
        result = rs.set_render_passes(["mist", "z", "shadow_catcher", "transparent"])
        assert set(result["changed"]) == {"mist", "z", "shadow_catcher", "transparent"}

    def test_pass_outside_the_map_refused_by_the_addon(self, scene):
        reply = server.get_connection().send_command("set_render_passes",
                                                     {"passes": ["__class__"]})
        assert reply["status"] == "error" and "__class__" in reply["result"]

    def test_ray_visibility(self, scene):
        result = rs.set_object_ray_visibility("Cube", camera=False, shadow_catcher=True)
        assert result["camera"] is False and result["shadow_catcher"] is True

    def test_ray_visibility_missing_object(self, scene):
        with pytest.raises(RuntimeError, match="Ghost"):
            rs.set_object_ray_visibility("Ghost", camera=False)

    def test_eevee_shadow_pool_size_is_an_enum_in_blender(self, scene):
        assert rs.set_eevee_quality(shadow_pool_size=512)["shadow_pool_size"] == 512

    def test_performance(self, scene):
        result = rs.set_render_performance(simplify=True, max_subdivision=2,
                                           persistent_data=True)
        assert result["simplify"] is True and result["max_subdivision"] == 2
        assert result["persistent_data"] is True


class TestLightGroupsAndAOVs:
    def test_create_assign_reuse_and_remove(self, scene):
        r1 = rs.set_light_group("Key.main", objects=["Light"])
        assert r1["group"] == "Key_main"  # Blender's own name for it
        rs.set_light_group("Key_main", world=True)
        groups = {g["name"]: g for g in rs.set_light_group("Rim", objects=["Cube"])["groups"]}
        assert groups["Key_main"] == {"name": "Key_main", "objects": ["Light"], "world": True}
        after = rs.set_light_group("Key_main", remove=True)["groups"]
        assert [g["name"] for g in after] == ["Rim"]

    def test_missing_object_assigns_nothing(self, scene):
        with pytest.raises(RuntimeError, match="Ghost"):
            rs.set_light_group("Key", objects=["Light", "Ghost"])
        assert rs.manage_aov("LIST") == {"aovs": []}  # still answers

    def test_remove_missing_group(self, scene):
        with pytest.raises(RuntimeError, match="Nope"):
            rs.set_light_group("Nope", remove=True)

    def test_aovs(self, scene):
        assert rs.manage_aov("ADD", name="mask", type="VALUE")["aovs"] == [
            {"name": "mask", "type": "VALUE"}]
        with pytest.raises(RuntimeError, match="already"):
            rs.manage_aov("ADD", name="mask", type="COLOR")
        assert rs.manage_aov("REMOVE", name="mask")["aovs"] == []
        with pytest.raises(RuntimeError, match="mask"):
            rs.manage_aov("REMOVE", name="mask")
