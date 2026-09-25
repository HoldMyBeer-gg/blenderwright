"""Mesh tools can act on the current selection instead of everything.

Sixteen tools called select_all(action="SELECT") before acting, so an agent
that had carefully selected the top face got its whole mesh beveled. The
selection tools added alongside this were useless until the tools that read
them existed.

The default stays ALL, so nothing that worked before changes. selection=
"CURRENT" is opt-in and means "use what is already selected", which is the
state Blender keeps on the mesh regardless.
"""

import pytest
from unittest.mock import MagicMock, patch

from blend_ai.validators import ValidationError

# Tools whose handler used to select the whole mesh first.
SELECTION_AWARE = [
    ("mesh_editing", "inset_faces", {"object_name": "Cube"}),
    ("mesh_editing", "dissolve_faces", {"object_name": "Cube"}),
    ("mesh_editing", "dissolve_edges", {"object_name": "Cube"}),
    ("mesh_editing", "dissolve_verts", {"object_name": "Cube"}),
    ("mesh_editing", "recalculate_normals", {"object_name": "Cube"}),
    ("mesh_editing", "flip_normals", {"object_name": "Cube"}),
    ("mesh_editing", "mark_seam", {"object_name": "Cube"}),
    ("mesh_editing", "mark_sharp", {"object_name": "Cube"}),
    ("modeling", "bevel_edges", {"object_name": "Cube", "width": 0.02}),
    ("modeling", "subdivide_mesh", {"object_name": "Cube"}),
]


@pytest.fixture
def conns():
    mocks = {}
    patches = []
    for module in ("mesh_editing", "modeling"):
        mock = MagicMock()
        mock.send_command.return_value = {"status": "ok", "result": {}}
        mocks[module] = mock
        patches.append(patch(f"blend_ai.tools.{module}.get_connection",
                             return_value=mock))
    for p in patches:
        p.start()
    yield mocks
    for p in patches:
        p.stop()


class TestSelectionParameter:
    @pytest.mark.parametrize("module,tool,kwargs", SELECTION_AWARE)
    def test_defaults_to_all_so_nothing_changes(self, conns, module, tool, kwargs):
        mod = __import__(f"blend_ai.tools.{module}", fromlist=[tool])
        getattr(mod, tool)(**kwargs)
        assert conns[module].send_command.call_args[0][1]["selection"] == "ALL"

    @pytest.mark.parametrize("module,tool,kwargs", SELECTION_AWARE)
    def test_current_is_passed_through(self, conns, module, tool, kwargs):
        mod = __import__(f"blend_ai.tools.{module}", fromlist=[tool])
        getattr(mod, tool)(selection="CURRENT", **kwargs)
        assert conns[module].send_command.call_args[0][1]["selection"] == "CURRENT"

    @pytest.mark.parametrize("module,tool,kwargs", SELECTION_AWARE)
    def test_an_unknown_selection_is_rejected(self, conns, module, tool, kwargs):
        mod = __import__(f"blend_ai.tools.{module}", fromlist=[tool])
        with pytest.raises(ValidationError):
            getattr(mod, tool)(selection="SOME", **kwargs)

    def test_the_allowed_values_are_documented_as_an_enum(self):
        """A model should not have to guess between two strings."""
        from blend_ai.tools.mesh_editing import ALLOWED_SELECTION_MODES
        assert ALLOWED_SELECTION_MODES == {"ALL", "CURRENT"}


class TestEveryClobberingHandlerWasCovered:
    # Two handlers select everything for reasons of their own, not because
    # they ignore the caller:
    #   separate_mesh already honours the selection through its own `type`
    #     parameter. type="SELECTED" uses the current selection; LOOSE and
    #     MATERIAL genuinely need the whole mesh.
    #   knife_project needs the cutter selected and the target active. Its
    #     select_all is part of that dance, not a clobber.
    EXEMPT = {"mesh_editing.py:handle_knife_project",
              "modeling.py:handle_separate_mesh"}

    def test_no_handler_still_unconditionally_selects_everything(self):
        """The whole point: none of them may ignore the caller's selection."""
        import re
        from pathlib import Path
        root = Path(__file__).parent.parent.parent / "addon" / "handlers"
        offenders = []
        for name in ("mesh_editing.py", "modeling.py"):
            source = (root / name).read_text()
            for match in re.finditer(r"^def (handle_\w+)", source, re.M):
                start = match.start()
                end = source.find("\ndef ", start + 1)
                body = source[start:end if end != -1 else len(source)]
                if "select_all(action=\"SELECT\")" in body and "selection" not in body:
                    key = f"{name}:{match.group(1)}"
                    if key not in self.EXEMPT:
                        offenders.append(key)
        assert not offenders, (
            f"these still select everything regardless of the caller: {offenders}"
        )

    def test_separate_mesh_honours_selection_through_its_own_parameter(self, conns):
        """type="SELECTED" is how separate_mesh has always read the selection."""
        from blend_ai.tools.modeling import separate_mesh
        separate_mesh("Cube", type="SELECTED")
        assert conns["modeling"].send_command.call_args[0][1]["type"] == "SELECTED"

    @pytest.mark.parametrize("module,tool", [("modeling", "separate_mesh"),
                                             ("mesh_editing", "knife_project")])
    def test_exempt_tools_do_not_advertise_a_parameter_nothing_reads(
            self, module, tool):
        """Their handlers ignore `selection`, so offering it would be a lie.

        A parameter accepted and then discarded is the worst failure mode
        available: it costs no round trip, so nothing signals the mistake.
        """
        import inspect
        mod = __import__(f"blend_ai.tools.{module}", fromlist=[tool])
        assert "selection" not in inspect.signature(getattr(mod, tool)).parameters


class TestInsetWasANoOpOnClosedMeshes:
    """inset_faces did nothing at all on any closed mesh, and said it worked.

    Measured in Blender 5.1 on a default cube: with the whole mesh selected,
    which is what the handler always did, inset leaves 8 vertices, 12 edges
    and 6 faces exactly as they were. A closed region has no boundary to
    inset from.

        selection=ALL      6 faces -> 6 faces   (nothing happened)
        selection=CURRENT  6 faces -> 10 faces  (one face inset properly)

    So this parameter is not only a refinement; it is the first time the tool
    does anything on a solid object.
    """

    def test_the_docstring_warns_about_closed_meshes(self):
        from blend_ai.tools.mesh_editing import inset_faces
        doc = inset_faces.__doc__ or ""
        assert "closed" in doc.lower(), (
            "a caller insetting a cube with the default gets silence; say so"
        )
