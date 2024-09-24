import numpy as np

from weave.legacy.weave import artifact_fs, artifact_wandb
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.ops_domain import table

from ...legacy.weave import types_numpy as numpy_types


def test_construct_numpy_type():
    target_type = {
        "type": "ndarray",
        "serializationPath": {
            "key": "some_key",
            "path": "a/b/c.npz",
        },
        "shape": [],
    }
    # should not raise
    t = numpy_types.NumpyArrayType.from_dict(target_type)

    # the following array should be assignable to t
    arr = np.array(1)
    t_inferred = types.TypeRegistry.type_of(arr)
    assert t_inferred.assign_type(t)


def test_construct_numpy_type_from_table_file():
    data = {
        "_type": "table",
        "column_types": {
            "params": {
                "type_map": {
                    "tca": {
                        "params": {
                            "allowed_types": [
                                {"wb_type": "none"},
                                {"wb_type": "string"},
                            ]
                        },
                        "wb_type": "union",
                    },
                    "pxe": {
                        "params": {
                            "allowed_types": [
                                {"wb_type": "none"},
                                {"wb_type": "string"},
                            ]
                        },
                        "wb_type": "union",
                    },
                    "gmi": {
                        "params": {
                            "allowed_types": [
                                {
                                    "params": {
                                        "box_layers": {
                                            "params": {"is_set": False, "val": {}},
                                            "wb_type": "const",
                                        },
                                        "box_score_keys": {
                                            "params": {"is_set": True, "val": []},
                                            "wb_type": "const",
                                        },
                                        "class_map": {
                                            "params": {"is_set": False, "val": {}},
                                            "wb_type": "const",
                                        },
                                        "mask_layers": {
                                            "params": {"is_set": False, "val": {}},
                                            "wb_type": "const",
                                        },
                                    },
                                    "wb_type": "image-file",
                                },
                                {"wb_type": "none"},
                            ]
                        },
                        "wb_type": "union",
                    },
                    "sbo": {
                        "params": {
                            "allowed_types": [
                                {"wb_type": "none"},
                                {
                                    "params": {
                                        "type_map": {
                                            "direction": {"wb_type": "number"},
                                            "image": {
                                                "params": {
                                                    "serialization_path": None,
                                                    "shape": [3, 3, 3],
                                                },
                                                "wb_type": "ndarray",
                                            },
                                            "mission": {"wb_type": "string"},
                                        }
                                    },
                                    "wb_type": "typedDict",
                                },
                            ]
                        },
                        "wb_type": "union",
                    },
                    "txet": {
                        "params": {
                            "allowed_types": [
                                {"wb_type": "none"},
                                {"wb_type": "string"},
                            ]
                        },
                        "wb_type": "union",
                    },
                }
            },
            "wb_type": "typedDict",
        },
        "columns": ["gmi", "sbo", "txet", "tca", "pxe"],
        "data": [
            [
                {
                    "_type": "image-file",
                    "format": "png",
                    "height": 192,
                    "path": "media/images/test.png",
                    "sha256": "blank",
                    "width": 352,
                },
                {
                    "direction": 0,
                    "image": [
                        [[1, 2, 3], [1, 4, 5], [1, 4, 20]],
                        [[1, 2, 3], [1, 4, 5], [10, 3, 2]],
                        [[1, 3, 3], [1, 4, 5], [1, -1, 2]],
                    ],
                    "mission": "test",
                },
                "blah",
                "blah",
                "blah2",
            ]
        ],
        "ncols": 5,
        "nrows": 1,
    }

    # generate a dummy filesystem artifact file so we can call
    # _get_rows_and_object_type_from_weave_format. that function
    # requires a filesystemartifactfile, but doesn't actually use it.
    # thus we can just use a dummy here.

    art = artifact_wandb.WandbArtifact("test")
    fs_artifact_file = artifact_fs.FilesystemArtifactFile(art, "test")
    _, object_type = table._get_rows_and_object_type_from_weave_format(
        data, fs_artifact_file
    )

    assert types.List(types.List(types.List(types.Int()))).assign_type(
        object_type.property_types["sbo"].property_types["image"]
    )
