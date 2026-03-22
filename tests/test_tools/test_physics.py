"""Unit tests for physics tools."""

import pytest
from unittest.mock import patch, MagicMock

from blend_ai.validators import ValidationError, MAX_PARTICLE_COUNT


@pytest.fixture
def mock_conn():
    mock = MagicMock()
    mock.send_command.return_value = {"status": "ok", "result": {"success": True}}
    with patch("blend_ai.tools.physics.get_connection", return_value=mock):
        yield mock


class TestAddRigidBody:
    def test_add_rigid_body_defaults(self, mock_conn):
        from blend_ai.tools.physics import add_rigid_body

        add_rigid_body("Cube")
        mock_conn.send_command.assert_called_once_with("add_rigid_body", {
            "object_name": "Cube",
            "type": "ACTIVE",
            "mass": 1.0,
            "friction": 0.5,
            "restitution": 0.0,
        })

    def test_add_rigid_body_passive(self, mock_conn):
        from blend_ai.tools.physics import add_rigid_body

        add_rigid_body("Floor", type="PASSIVE", mass=0.001, friction=0.8, restitution=0.3)
        mock_conn.send_command.assert_called_once_with("add_rigid_body", {
            "object_name": "Floor",
            "type": "PASSIVE",
            "mass": 0.001,
            "friction": 0.8,
            "restitution": 0.3,
        })

    def test_invalid_rigid_body_type(self, mock_conn):
        from blend_ai.tools.physics import add_rigid_body

        with pytest.raises(ValidationError):
            add_rigid_body("Cube", type="DYNAMIC")

    def test_friction_out_of_range(self, mock_conn):
        from blend_ai.tools.physics import add_rigid_body

        with pytest.raises(ValidationError):
            add_rigid_body("Cube", friction=-0.1)
        with pytest.raises(ValidationError):
            add_rigid_body("Cube", friction=1.1)

    def test_restitution_out_of_range(self, mock_conn):
        from blend_ai.tools.physics import add_rigid_body

        with pytest.raises(ValidationError):
            add_rigid_body("Cube", restitution=-0.1)
        with pytest.raises(ValidationError):
            add_rigid_body("Cube", restitution=1.1)

    def test_mass_out_of_range(self, mock_conn):
        from blend_ai.tools.physics import add_rigid_body

        with pytest.raises(ValidationError):
            add_rigid_body("Cube", mass=0.0)


class TestAddClothSim:
    def test_add_cloth_defaults(self, mock_conn):
        from blend_ai.tools.physics import add_cloth_sim

        add_cloth_sim("Plane")
        mock_conn.send_command.assert_called_once_with("add_cloth_sim", {
            "object_name": "Plane",
            "quality": 5,
            "mass": 0.3,
        })

    def test_add_cloth_custom(self, mock_conn):
        from blend_ai.tools.physics import add_cloth_sim

        add_cloth_sim("Plane", quality=20, mass=1.5)
        mock_conn.send_command.assert_called_once()

    def test_quality_out_of_range(self, mock_conn):
        from blend_ai.tools.physics import add_cloth_sim

        with pytest.raises(ValidationError):
            add_cloth_sim("Plane", quality=0)
        with pytest.raises(ValidationError):
            add_cloth_sim("Plane", quality=81)

    def test_mass_out_of_range(self, mock_conn):
        from blend_ai.tools.physics import add_cloth_sim

        with pytest.raises(ValidationError):
            add_cloth_sim("Plane", mass=0.0)


class TestAddFluidSim:
    def test_add_fluid_domain_gas(self, mock_conn):
        from blend_ai.tools.physics import add_fluid_sim

        add_fluid_sim("Cube", type="DOMAIN", domain_type="GAS")
        mock_conn.send_command.assert_called_once_with("add_fluid_sim", {
            "object_name": "Cube",
            "type": "DOMAIN",
            "domain_type": "GAS",
        })

    def test_add_fluid_domain_liquid(self, mock_conn):
        from blend_ai.tools.physics import add_fluid_sim

        add_fluid_sim("Cube", type="DOMAIN", domain_type="LIQUID")
        mock_conn.send_command.assert_called_once()

    def test_add_fluid_flow(self, mock_conn):
        from blend_ai.tools.physics import add_fluid_sim

        add_fluid_sim("Sphere", type="FLOW")
        mock_conn.send_command.assert_called_once()

    def test_add_fluid_effector(self, mock_conn):
        from blend_ai.tools.physics import add_fluid_sim

        add_fluid_sim("Wall", type="EFFECTOR")
        mock_conn.send_command.assert_called_once()

    def test_invalid_fluid_type(self, mock_conn):
        from blend_ai.tools.physics import add_fluid_sim

        with pytest.raises(ValidationError):
            add_fluid_sim("Cube", type="INFLOW")

    def test_invalid_domain_type(self, mock_conn):
        from blend_ai.tools.physics import add_fluid_sim

        with pytest.raises(ValidationError):
            add_fluid_sim("Cube", type="DOMAIN", domain_type="FOAM")


class TestAddParticleSystem:
    def test_add_particles_defaults(self, mock_conn):
        from blend_ai.tools.physics import add_particle_system

        add_particle_system("Cube")
        mock_conn.send_command.assert_called_once_with("add_particle_system", {
            "object_name": "Cube",
            "count": 1000,
            "lifetime": 50.0,
            "emit_from": "FACE",
        })

    def test_add_particles_custom(self, mock_conn):
        from blend_ai.tools.physics import add_particle_system

        add_particle_system("Cube", count=5000, lifetime=100.0, emit_from="VOLUME")
        mock_conn.send_command.assert_called_once()

    def test_particle_count_capped_at_max(self, mock_conn):
        from blend_ai.tools.physics import add_particle_system

        with pytest.raises(ValidationError):
            add_particle_system("Cube", count=MAX_PARTICLE_COUNT + 1)

    def test_particle_count_max_accepted(self, mock_conn):
        from blend_ai.tools.physics import add_particle_system

        add_particle_system("Cube", count=MAX_PARTICLE_COUNT)
        mock_conn.send_command.assert_called_once()

    def test_particle_count_min(self, mock_conn):
        from blend_ai.tools.physics import add_particle_system

        with pytest.raises(ValidationError):
            add_particle_system("Cube", count=0)

    def test_invalid_emit_from(self, mock_conn):
        from blend_ai.tools.physics import add_particle_system

        with pytest.raises(ValidationError):
            add_particle_system("Cube", emit_from="EDGE")

    def test_all_emit_from_valid(self, mock_conn):
        from blend_ai.tools.physics import add_particle_system, ALLOWED_EMIT_FROM

        for ef in ALLOWED_EMIT_FROM:
            mock_conn.send_command.reset_mock()
            add_particle_system("Cube", emit_from=ef)
            mock_conn.send_command.assert_called_once()


class TestSetPhysicsProperty:
    def test_set_physics_property(self, mock_conn):
        from blend_ai.tools.physics import set_physics_property

        set_physics_property("Cube", "RIGID_BODY", "mass", 5.0)
        mock_conn.send_command.assert_called_once_with("set_physics_property", {
            "object_name": "Cube",
            "physics_type": "RIGID_BODY",
            "property": "mass",
            "value": 5.0,
        })

    def test_invalid_physics_type(self, mock_conn):
        from blend_ai.tools.physics import set_physics_property

        with pytest.raises(ValidationError):
            set_physics_property("Cube", "SOFT_BODY", "mass", 1.0)

    def test_empty_property(self, mock_conn):
        from blend_ai.tools.physics import set_physics_property

        with pytest.raises(ValidationError, match="property must be a non-empty string"):
            set_physics_property("Cube", "CLOTH", "", 1.0)


class TestBakePhysics:
    def test_bake_all(self, mock_conn):
        from blend_ai.tools.physics import bake_physics

        bake_physics("Cube")
        mock_conn.send_command.assert_called_once_with("bake_physics", {
            "object_name": "Cube",
            "physics_type": "",
        })

    def test_bake_specific_type(self, mock_conn):
        from blend_ai.tools.physics import bake_physics

        bake_physics("Cube", physics_type="CLOTH")
        mock_conn.send_command.assert_called_once_with("bake_physics", {
            "object_name": "Cube",
            "physics_type": "CLOTH",
        })

    def test_bake_invalid_type(self, mock_conn):
        from blend_ai.tools.physics import bake_physics

        with pytest.raises(ValidationError):
            bake_physics("Cube", physics_type="SOFT_BODY")

    def test_bake_invalid_name(self, mock_conn):
        from blend_ai.tools.physics import bake_physics

        with pytest.raises(ValidationError):
            bake_physics("")


class TestBlenderErrorHandling:
    def test_blender_error_raises_runtime(self, mock_conn):
        from blend_ai.tools.physics import add_rigid_body

        mock_conn.send_command.return_value = {"status": "error", "result": "Object not found"}
        with pytest.raises(RuntimeError, match="Blender error"):
            add_rigid_body("Cube")
