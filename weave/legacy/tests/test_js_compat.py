# This file should include tests for all the fixups we do to match
# the frontend js code.
# The related sites should be tagged with "# NOTE: js_compat" in the
#     Weave python code.
# TODO: Fix all the non-standard behaviors in the weave js code so we
#     can get rid of this file.
# Note: This file is not yet complete, there are existing fixups in the
#     weave Python code that I haven't documented here.

from weave.legacy.weave import partial_object, weavejs_fixes
from weave.legacy.weave import weave_types as types
from weave.legacy.weave.ops_domain import wb_domain_types


def test_const_serialization():
    f_type = types.FileType(types.Const(types.String(), "png"))
    f_type_dict = f_type.to_dict()
    assert f_type_dict == {"extension": "png", "type": "FileBase"}
    f_type2 = types.TypeRegistry.type_from_dict(f_type_dict)
    assert isinstance(f_type2, types.FileType)
    assert isinstance(f_type2.extension, types.Const)
    assert f_type2.extension.val == "png"


def test_partialobject_type_stripping():
    instance = wb_domain_types.Run({"a": types.String()})
    type = types.TypeRegistry.type_of(instance)
    assert isinstance(type, partial_object.PartialObjectType)
    serialized = type.to_dict()
    assert weavejs_fixes.remove_partialobject_from_types(serialized) == "run"


def test_nested_partialobject_type_stripping():
    input = {
        "type": "tagged",
        "tag": {
            "type": "typedDict",
            "propertyTypes": {
                "project": {
                    "type": "PartialObject",
                    "keys": {
                        "id": "string",
                        "name": "string",
                        "runs_b7f2f1441a601b3477d356429a493d05": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "edges": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "node": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "id": "string",
                                                    "name": "string",
                                                    "summaryMetrics": "string",
                                                },
                                            }
                                        },
                                    },
                                }
                            },
                        },
                    },
                    "keyless_weave_type_class": "project",
                }
            },
        },
        "value": {
            "type": "list",
            "objectType": {
                "type": "union",
                "members": [
                    {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": {
                                    "type": "PartialObject",
                                    "keys": {
                                        "id": "string",
                                        "name": "string",
                                        "summaryMetrics": "string",
                                    },
                                    "keyless_weave_type_class": "run",
                                }
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "epoch": "int",
                                "_timestamp": "float",
                                "samples_wf_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "val_mean_absolute_error": "float",
                                "graph": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "sha256": "string",
                                        "path": "string",
                                        "size": "int",
                                        "_type": "string",
                                    },
                                },
                                "best_epoch": "int",
                                "samples_wf_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "final_val_loss": "float",
                                "_step": "int",
                                "val_mae": "float",
                                "_runtime": "float",
                                "test_loss": "float",
                                "samples_wf_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "mean_absolute_error": "float",
                                "loss": "float",
                                "GFLOPs": "int",
                                "test_mae": "float",
                                "val_loss": "float",
                                "best_val_loss": "float",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": {
                                    "type": "PartialObject",
                                    "keys": {
                                        "id": "string",
                                        "name": "string",
                                        "summaryMetrics": "string",
                                    },
                                    "keyless_weave_type_class": "run",
                                }
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "_step": "int",
                                "_runtime": "float",
                                "samples_wf_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_timestamp": "float",
                                "samples_wf_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": {
                                    "type": "PartialObject",
                                    "keys": {
                                        "id": "string",
                                        "name": "string",
                                        "summaryMetrics": "string",
                                    },
                                    "keyless_weave_type_class": "run",
                                }
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "samples_wf_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "best_val_loss": "float",
                                "final_val_loss": "float",
                                "graph": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "sha256": "string",
                                        "path": "string",
                                        "size": "int",
                                        "_type": "string",
                                    },
                                },
                                "best_epoch": "int",
                                "_timestamp": "float",
                                "samples_wf_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "val_mean_absolute_error": "float",
                                "epoch": "int",
                                "test_mae": "float",
                                "val_loss": "float",
                                "loss": "float",
                                "_runtime": "float",
                                "mean_absolute_error": "float",
                                "samples_wf_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_step": "int",
                                "val_mae": "float",
                                "test_loss": "float",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": {
                                    "type": "PartialObject",
                                    "keys": {
                                        "id": "string",
                                        "name": "string",
                                        "summaryMetrics": "string",
                                    },
                                    "keyless_weave_type_class": "run",
                                }
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "samples_wf_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_runtime": "float",
                                "test_mae": "float",
                                "val_mae": "float",
                                "test_loss": "float",
                                "_timestamp": "float",
                                "samples_wf_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "final_val_loss": "float",
                                "_step": "int",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": {
                                    "type": "PartialObject",
                                    "keys": {
                                        "id": "string",
                                        "name": "string",
                                        "summaryMetrics": "string",
                                    },
                                    "keyless_weave_type_class": "run",
                                }
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "samples_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_timestamp": "float",
                                "_step": "int",
                                "_runtime": "float",
                                "samples_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": {
                                    "type": "PartialObject",
                                    "keys": {
                                        "id": "string",
                                        "name": "string",
                                        "summaryMetrics": "string",
                                    },
                                    "keyless_weave_type_class": "run",
                                }
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "loss": "float",
                                "GFLOPs": "int",
                                "_runtime": "float",
                                "samples_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "best_epoch": "int",
                                "val_mean_absolute_error": "float",
                                "test_loss": "float",
                                "_step": "int",
                                "epoch": "int",
                                "graph": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "path": "string",
                                        "size": "int",
                                        "_type": "string",
                                        "sha256": "string",
                                    },
                                },
                                "val_loss": "float",
                                "samples_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_timestamp": "float",
                                "best_val_loss": "float",
                                "final_val_loss": "float",
                                "mean_absolute_error": "float",
                                "val_mae": "float",
                                "test_mae": "float",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": {
                                    "type": "PartialObject",
                                    "keys": {
                                        "id": "string",
                                        "name": "string",
                                        "summaryMetrics": "string",
                                    },
                                    "keyless_weave_type_class": "run",
                                }
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "_step": "int",
                                "graph": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "path": "string",
                                        "size": "int",
                                        "_type": "string",
                                        "sha256": "string",
                                    },
                                },
                                "samples_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "val_mean_absolute_error": "float",
                                "samples_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "final_val_loss": "float",
                                "epoch": "int",
                                "_runtime": "float",
                                "test_mae": "float",
                                "samples_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_timestamp": "float",
                                "best_epoch": "int",
                                "best_val_loss": "float",
                                "loss": "float",
                                "val_mae": "float",
                                "val_loss": "float",
                                "samples_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "test_loss": "float",
                                "mean_absolute_error": "float",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": {
                                    "type": "PartialObject",
                                    "keys": {
                                        "id": "string",
                                        "name": "string",
                                        "summaryMetrics": "string",
                                    },
                                    "keyless_weave_type_class": "run",
                                }
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "val_mae": "float",
                                "samples_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "test_loss": "float",
                                "_timestamp": "float",
                                "_step": "int",
                                "_runtime": "float",
                                "test_mae": "float",
                                "samples_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "final_val_loss": "float",
                            },
                        },
                    },
                ],
            },
        },
    }

    actual = weavejs_fixes.remove_partialobject_from_types(input)

    expected = {
        "type": "tagged",
        "tag": {"type": "typedDict", "propertyTypes": {"project": "project"}},
        "value": {
            "type": "list",
            "objectType": {
                "type": "union",
                "members": [
                    {
                        "type": "tagged",
                        "tag": {"type": "typedDict", "propertyTypes": {"run": "run"}},
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "epoch": "int",
                                "_timestamp": "float",
                                "samples_wf_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "val_mean_absolute_error": "float",
                                "graph": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "sha256": "string",
                                        "path": "string",
                                        "size": "int",
                                        "_type": "string",
                                    },
                                },
                                "best_epoch": "int",
                                "samples_wf_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "final_val_loss": "float",
                                "_step": "int",
                                "val_mae": "float",
                                "_runtime": "float",
                                "test_loss": "float",
                                "samples_wf_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "mean_absolute_error": "float",
                                "loss": "float",
                                "GFLOPs": "int",
                                "test_mae": "float",
                                "val_loss": "float",
                                "best_val_loss": "float",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {"type": "typedDict", "propertyTypes": {"run": "run"}},
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "_step": "int",
                                "_runtime": "float",
                                "samples_wf_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_timestamp": "float",
                                "samples_wf_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {"type": "typedDict", "propertyTypes": {"run": "run"}},
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "samples_wf_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "best_val_loss": "float",
                                "final_val_loss": "float",
                                "graph": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "sha256": "string",
                                        "path": "string",
                                        "size": "int",
                                        "_type": "string",
                                    },
                                },
                                "best_epoch": "int",
                                "_timestamp": "float",
                                "samples_wf_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "val_mean_absolute_error": "float",
                                "epoch": "int",
                                "test_mae": "float",
                                "val_loss": "float",
                                "loss": "float",
                                "_runtime": "float",
                                "mean_absolute_error": "float",
                                "samples_wf_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_step": "int",
                                "val_mae": "float",
                                "test_loss": "float",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {"type": "typedDict", "propertyTypes": {"run": "run"}},
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "samples_wf_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_runtime": "float",
                                "test_mae": "float",
                                "val_mae": "float",
                                "test_loss": "float",
                                "_timestamp": "float",
                                "samples_wf_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_wf_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "final_val_loss": "float",
                                "_step": "int",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {"type": "typedDict", "propertyTypes": {"run": "run"}},
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "samples_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_timestamp": "float",
                                "_step": "int",
                                "_runtime": "float",
                                "samples_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {"type": "typedDict", "propertyTypes": {"run": "run"}},
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "loss": "float",
                                "GFLOPs": "int",
                                "_runtime": "float",
                                "samples_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "best_epoch": "int",
                                "val_mean_absolute_error": "float",
                                "test_loss": "float",
                                "_step": "int",
                                "epoch": "int",
                                "graph": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "path": "string",
                                        "size": "int",
                                        "_type": "string",
                                        "sha256": "string",
                                    },
                                },
                                "val_loss": "float",
                                "samples_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_timestamp": "float",
                                "best_val_loss": "float",
                                "final_val_loss": "float",
                                "mean_absolute_error": "float",
                                "val_mae": "float",
                                "test_mae": "float",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {"type": "typedDict", "propertyTypes": {"run": "run"}},
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "_step": "int",
                                "graph": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "path": "string",
                                        "size": "int",
                                        "_type": "string",
                                        "sha256": "string",
                                    },
                                },
                                "samples_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "val_mean_absolute_error": "float",
                                "samples_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "final_val_loss": "float",
                                "epoch": "int",
                                "_runtime": "float",
                                "test_mae": "float",
                                "samples_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "_timestamp": "float",
                                "best_epoch": "int",
                                "best_val_loss": "float",
                                "loss": "float",
                                "val_mae": "float",
                                "val_loss": "float",
                                "samples_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "test_loss": "float",
                                "mean_absolute_error": "float",
                            },
                        },
                    },
                    {
                        "type": "tagged",
                        "tag": {"type": "typedDict", "propertyTypes": {"run": "run"}},
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "val_mae": "float",
                                "samples_0": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_1": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_3": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "samples_4": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "test_loss": "float",
                                "_timestamp": "float",
                                "_step": "int",
                                "_runtime": "float",
                                "test_mae": "float",
                                "samples_2": {
                                    "type": "file",
                                    "_base_type": {"type": "FileBase"},
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "_base_type": {"type": "Object"},
                                        "_is_object": True,
                                        "_rows": {
                                            "type": "ArrowWeaveList",
                                            "_base_type": {"type": "list"},
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {},
                                            },
                                        },
                                    },
                                },
                                "final_val_loss": "float",
                            },
                        },
                    },
                ],
            },
        },
    }

    assert actual == expected
