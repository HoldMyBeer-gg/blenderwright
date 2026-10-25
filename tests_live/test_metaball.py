"""Metaballs in a real Blender: elements blend, negatives carve, it becomes a mesh."""


from blenderwright.tools.objects import convert_object, create_metaball, get_object_info


def test_two_balls_merge_into_one_shape(scene):
    create_metaball("Blob", elements=[
        {"type": "BALL", "location": [0, 0, 0], "radius": 1},
        {"type": "BALL", "location": [1.2, 0, 0], "radius": 1},
    ])
    info = get_object_info("Blob")
    assert info["type"] == "META"
    assert info["dimensions"][0] > info["dimensions"][1] * 1.5  # one long blob


def test_negative_element_carves(scene):
    create_metaball("Full", elements=[{"type": "BALL", "radius": 1}])
    create_metaball("Bitten", location=[5, 0, 0], elements=[
        {"type": "BALL", "radius": 1},
        {"type": "BALL", "location": [0.6, 0, 0], "radius": 0.8, "negative": True},
    ])
    assert get_object_info("Bitten")["dimensions"][0] < get_object_info("Full")["dimensions"][0]


def test_converts_to_mesh(scene):
    create_metaball("Blob", elements=[{"type": "CAPSULE", "size": [1, 0.5, 0.5]}])
    convert_object("Blob", target="MESH")
    info = get_object_info("Blob")
    assert info["type"] == "MESH"
    assert info["dimensions"][0] > info["dimensions"][1] > 0  # a capsule stretched along X
