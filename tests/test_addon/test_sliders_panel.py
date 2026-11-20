"""The Sliders section of the N panel: which properties it shows, and when."""

import importlib.util
import os

ADDON = os.path.join(os.path.dirname(__file__), "..", "..", "addon")


def _load_sliders():
    spec = importlib.util.spec_from_file_location("addon_sliders", os.path.join(ADDON, "sliders.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_numbers_are_sliders_and_everything_else_is_not():
    props = {"Open": 0.5, "Count": 3, "flag": True, "_private": 1.0, "label": "hi",
             "cycles": {"x": 1}, "vec": [1.0, 2.0]}
    assert _load_sliders().slider_keys(props.items()) == ["Count", "Open"]


def test_no_numbers_no_sliders():
    assert _load_sliders().slider_keys({"label": "x"}.items()) == []


def test_panel_hides_itself_without_sliders_and_draws_them_as_sliders():
    src = open(os.path.join(ADDON, "ui_panel.py")).read()
    assert "class BLENDERWRIGHT_PT_Sliders" in src
    assert "def poll(" in src and "slider_keys(" in src
    assert "slider=True" in src
    assert "BLENDERWRIGHT_PT_Sliders," in src  # registered
