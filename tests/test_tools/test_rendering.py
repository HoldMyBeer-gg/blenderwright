"""Unit tests for rendering tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.rendering.get_connection", return_value=mock):
        yield mock


class TestSetRenderEngine:
    def test_set_cycles(self, mock_conn):
        from blend_ai.tools.rendering import set_render_engine

        set_render_engine("CYCLES")
        mock_conn.send_command.assert_called_once_with("set_render_engine", {"engine": "CYCLES"})

    def test_set_eevee(self, mock_conn):
        from blend_ai.tools.rendering import set_render_engine

        set_render_engine("BLENDER_EEVEE_NEXT")
        mock_conn.send_command.assert_called_once()

    def test_set_workbench(self, mock_conn):
        from blend_ai.tools.rendering import set_render_engine

        set_render_engine("BLENDER_WORKBENCH")
        mock_conn.send_command.assert_called_once()

    def test_invalid_engine(self, mock_conn):
        from blend_ai.tools.rendering import set_render_engine

        with pytest.raises(ValidationError):
            set_render_engine("BLENDER_EEVEE")  # old name, not allowed

    def test_invalid_engine_arbitrary(self, mock_conn):
        from blend_ai.tools.rendering import set_render_engine

        with pytest.raises(ValidationError):
            set_render_engine("LUXCORE")


class TestSetRenderResolution:
    def test_set_resolution(self, mock_conn):
        from blend_ai.tools.rendering import set_render_resolution

        set_render_resolution(1920, 1080)
        mock_conn.send_command.assert_called_once_with("set_render_resolution", {
            "width": 1920,
            "height": 1080,
            "percentage": 100,
        })

    def test_set_resolution_with_percentage(self, mock_conn):
        from blend_ai.tools.rendering import set_render_resolution

        set_render_resolution(3840, 2160, percentage=50)
        mock_conn.send_command.assert_called_once_with("set_render_resolution", {
            "width": 3840,
            "height": 2160,
            "percentage": 50,
        })

    def test_resolution_capped_at_8192(self, mock_conn):
        from blend_ai.tools.rendering import set_render_resolution

        with pytest.raises(ValidationError):
            set_render_resolution(8193, 1080)
        with pytest.raises(ValidationError):
            set_render_resolution(1920, 8193)

    def test_resolution_min_1(self, mock_conn):
        from blend_ai.tools.rendering import set_render_resolution

        with pytest.raises(ValidationError):
            set_render_resolution(0, 1080)

    def test_percentage_out_of_range(self, mock_conn):
        from blend_ai.tools.rendering import set_render_resolution

        with pytest.raises(ValidationError):
            set_render_resolution(1920, 1080, percentage=0)
        with pytest.raises(ValidationError):
            set_render_resolution(1920, 1080, percentage=101)

    def test_max_resolution_accepted(self, mock_conn):
        from blend_ai.tools.rendering import set_render_resolution

        set_render_resolution(8192, 8192)
        mock_conn.send_command.assert_called_once()


class TestSetRenderSamples:
    def test_set_samples(self, mock_conn):
        from blend_ai.tools.rendering import set_render_samples

        set_render_samples(128)
        mock_conn.send_command.assert_called_once_with("set_render_samples", {"samples": 128})

    def test_samples_capped_at_10000(self, mock_conn):
        from blend_ai.tools.rendering import set_render_samples

        with pytest.raises(ValidationError):
            set_render_samples(10001)

    def test_samples_max_accepted(self, mock_conn):
        from blend_ai.tools.rendering import set_render_samples

        set_render_samples(10000)
        mock_conn.send_command.assert_called_once()

    def test_samples_min_1(self, mock_conn):
        from blend_ai.tools.rendering import set_render_samples

        with pytest.raises(ValidationError):
            set_render_samples(0)


class TestSetOutputFormat:
    def test_set_png(self, mock_conn):
        from blend_ai.tools.rendering import set_output_format

        set_output_format("PNG")
        mock_conn.send_command.assert_called_once_with("set_output_format", {"format": "PNG"})

    def test_set_format_with_filepath(self, mock_conn):
        from blend_ai.tools.rendering import set_output_format

        set_output_format("JPEG", filepath="/tmp/output.jpg")
        call_args = mock_conn.send_command.call_args
        assert call_args[0][0] == "set_output_format"
        assert call_args[0][1]["format"] == "JPEG"
        assert "filepath" in call_args[0][1]

    def test_invalid_format(self, mock_conn):
        from blend_ai.tools.rendering import set_output_format

        with pytest.raises(ValidationError):
            set_output_format("GIF")

    def test_invalid_filepath_extension(self, mock_conn):
        from blend_ai.tools.rendering import set_output_format

        with pytest.raises(ValidationError):
            set_output_format("PNG", filepath="/tmp/output.gif")


class TestRenderImage:
    def test_render_image_default(self, mock_conn):
        from blend_ai.tools.rendering import render_image

        render_image()
        call_args = mock_conn.send_command.call_args
        assert call_args[0][0] == "render_image"
        assert call_args[0][1]["filepath"].endswith("render.png")

    def test_render_image_custom_path(self, mock_conn):
        from blend_ai.tools.rendering import render_image

        render_image(filepath="/tmp/my_render.exr")
        call_args = mock_conn.send_command.call_args
        assert call_args[0][1]["filepath"].endswith("my_render.exr")

    def test_render_image_invalid_extension(self, mock_conn):
        from blend_ai.tools.rendering import render_image

        with pytest.raises(ValidationError):
            render_image(filepath="/tmp/render.mp4")


class TestRenderAnimation:
    def test_render_animation_default(self, mock_conn):
        from blend_ai.tools.rendering import render_animation

        render_animation()
        mock_conn.send_command.assert_called_once_with("render_animation", {
            "filepath": "/tmp/render_",
            "format": "PNG",
        })

    def test_render_animation_custom(self, mock_conn):
        from blend_ai.tools.rendering import render_animation

        render_animation(filepath="/tmp/anim_", format="JPEG")
        mock_conn.send_command.assert_called_once_with("render_animation", {
            "filepath": "/tmp/anim_",
            "format": "JPEG",
        })

    def test_render_animation_invalid_format(self, mock_conn):
        from blend_ai.tools.rendering import render_animation

        with pytest.raises(ValidationError):
            render_animation(format="AVI")

    def test_render_animation_empty_filepath(self, mock_conn):
        from blend_ai.tools.rendering import render_animation

        with pytest.raises(ValidationError):
            render_animation(filepath="")

    def test_render_animation_null_byte_filepath(self, mock_conn):
        from blend_ai.tools.rendering import render_animation

        with pytest.raises(ValidationError):
            render_animation(filepath="/tmp/render\x00evil")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.rendering import set_render_engine

        mock_conn.send_command.return_value = {"status": "error", "result": "Engine not available"}
        with pytest.raises(RuntimeError, match="Blender error"):
            set_render_engine("CYCLES")
