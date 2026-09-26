"""point_camera_at: coordinates belong in `location`, not `target`.

`target` takes an object name and `location` takes XYZ; they are mutually
exclusive. Nothing in the name "target" says which, so coordinates get passed
to it, and the failure used to surface as "Object name must be a non-empty
string" -- true, but it never mentions the parameter that would have worked.
"""

import pytest
from unittest.mock import MagicMock, patch

from blend_ai.validators import ValidationError


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {}}
    with patch("blend_ai.tools.camera.get_connection", return_value=mock):
        yield mock


class TestTargetTakesAnObjectName:
    def test_object_name_is_sent(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at
        point_camera_at("Cam", target="Cube")
        assert mock_conn.send_command.call_args[0][1]["target"] == "Cube"

    def test_location_is_sent(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at
        point_camera_at("Cam", location=[1.0, 2.0, 3.0])
        assert mock_conn.send_command.call_args[0][1]["location"] == [1.0, 2.0, 3.0]


class TestCoordinatesInTarget:
    @pytest.mark.parametrize("coords", [[1.0, 2.0, 3.0], (1.0, 2.0, 3.0)])
    def test_rejected_with_a_message_naming_location(self, mock_conn, coords):
        from blend_ai.tools.camera import point_camera_at
        with pytest.raises(ValidationError) as exc:
            point_camera_at("Cam", target=coords)
        assert "location" in str(exc.value), (
            f"error must point at the right parameter, got: {exc.value}")

    def test_the_old_opaque_message_is_gone(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at
        with pytest.raises(ValidationError) as exc:
            point_camera_at("Cam", target=[1.0, 2.0, 3.0])
        assert "non-empty string" not in str(exc.value)

    def test_a_number_is_also_caught(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at
        with pytest.raises(ValidationError):
            point_camera_at("Cam", target=5.0)


class TestMutualExclusion:
    def test_neither_is_rejected(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at
        with pytest.raises(ValidationError):
            point_camera_at("Cam")

    def test_both_is_rejected(self, mock_conn):
        from blend_ai.tools.camera import point_camera_at
        with pytest.raises(ValidationError):
            point_camera_at("Cam", target="Cube", location=[1.0, 2.0, 3.0])
