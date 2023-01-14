from weave import graph_debug, serialize
from weave.server import _handle_request


def test_playback():
    for payload in execute_payloads:
        nodes = serialize.deserialize(payload["graphs"])
        print(
            "Executing %s leaf nodes.\n%s"
            % (
                len(nodes),
                "\n".join(
                    graph_debug.node_expr_str_full(n)
                    for n in graph_debug.combine_common_nodes(nodes)
                ),
            )
        )
        res = _handle_request(payload, True)
        assert "err" not in res


# Paste graphs below (from DD or Network tab to test)
execute_payloads: list[dict] = [
    {
    "graphs": {
        "nodes": [
            {
                "nodeType": "output",
                "fromOp": 1,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "4593977264364963"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 73
                }
            },
            {
                "nodeType": "output",
                "fromOp": 3,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "id": "1329574732475660"
            },
            {
                "name": "group-groupkey",
                "inputs": {
                    "obj": 4
                }
            },
            {
                "nodeType": "output",
                "fromOp": 5,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "groupKey": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "label": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "run": "run"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "4353553168884790"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 6,
                    "index": 72
                }
            },
            {
                "nodeType": "output",
                "fromOp": 7,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "groupKey": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "label": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "project": "project"
                                                        }
                                                    },
                                                    "value": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "run": "run"
                                                        }
                                                    }
                                                },
                                                "value": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        "float"
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "value": {
                                "type": "list",
                                "objectType": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "indexCheckpoint": "number"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "img": {
                                                "type": "union",
                                                "members": [
                                                    {
                                                        "type": "image-file",
                                                        "_is_object": True,
                                                        "path": {
                                                            "type": "ArtifactEntry"
                                                        },
                                                        "format": "string",
                                                        "height": "int",
                                                        "width": "int",
                                                        "sha256": "string"
                                                    },
                                                    "none"
                                                ]
                                            },
                                            "label": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "810749694946276"
            },
            {
                "name": "sort",
                "inputs": {
                    "arr": 8,
                    "compFn": 62,
                    "columnDirs": 71
                }
            },
            {
                "nodeType": "output",
                "fromOp": 9,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "groupKey": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "label": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "project": "project"
                                                        }
                                                    },
                                                    "value": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "run": "run"
                                                        }
                                                    }
                                                },
                                                "value": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        "float"
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "value": {
                                "type": "list",
                                "objectType": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "indexCheckpoint": "number"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "img": {
                                                "type": "union",
                                                "members": [
                                                    {
                                                        "type": "image-file",
                                                        "_is_object": True,
                                                        "path": {
                                                            "type": "ArtifactEntry"
                                                        },
                                                        "format": "string",
                                                        "height": "int",
                                                        "width": "int",
                                                        "sha256": "string"
                                                    },
                                                    "none"
                                                ]
                                            },
                                            "label": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "4664998879741159"
            },
            {
                "name": "groupby",
                "inputs": {
                    "arr": 10,
                    "groupByFn": 55
                }
            },
            {
                "nodeType": "output",
                "fromOp": 11,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "1393878607581578"
            },
            {
                "name": "filter",
                "inputs": {
                    "arr": 12,
                    "filterFn": 38
                }
            },
            {
                "nodeType": "output",
                "fromOp": 13,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "5427644232586845"
            },
            {
                "name": "list-createIndexCheckpointTag",
                "inputs": {
                    "arr": 14
                }
            },
            {
                "nodeType": "output",
                "fromOp": 15,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "run": "run"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "3945586850757548"
            },
            {
                "name": "concat",
                "inputs": {
                    "arr": 16
                }
            },
            {
                "nodeType": "output",
                "fromOp": 17,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "union",
                            "members": [
                                "none",
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    },
                                    "value": {
                                        "type": "list",
                                        "objectType": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "img": {
                                                    "type": "union",
                                                    "members": [
                                                        {
                                                            "type": "image-file",
                                                            "_is_object": True,
                                                            "path": {
                                                                "type": "ArtifactEntry"
                                                            },
                                                            "format": "string",
                                                            "height": "int",
                                                            "width": "int",
                                                            "sha256": "string"
                                                        },
                                                        "none"
                                                    ]
                                                },
                                                "label": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        "float"
                                                    ]
                                                }
                                            }
                                        },
                                        "minLength": 0
                                    }
                                }
                            ]
                        }
                    }
                },
                "id": "3598699934832222"
            },
            {
                "name": "dropna",
                "inputs": {
                    "arr": 18
                }
            },
            {
                "nodeType": "output",
                "fromOp": 19,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "union",
                            "members": [
                                "none",
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    },
                                    "value": {
                                        "type": "ArrowWeaveList",
                                        "_base_type": {
                                            "type": "list",
                                            "objectType": "any"
                                        },
                                        "objectType": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "img": {
                                                    "type": "union",
                                                    "members": [
                                                        {
                                                            "type": "image-file",
                                                            "_is_object": True,
                                                            "path": {
                                                                "type": "ArtifactEntry"
                                                            },
                                                            "format": "string",
                                                            "height": "int",
                                                            "width": "int",
                                                            "sha256": "string"
                                                        },
                                                        "none"
                                                    ]
                                                },
                                                "label": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        "float"
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                },
                "id": "3833780585822090"
            },
            {
                "name": "table-rows",
                "inputs": {
                    "table": 20
                }
            },
            {
                "nodeType": "output",
                "fromOp": 21,
                "type": {
                    "type": "list",
                    "objectType": {
                        "type": "union",
                        "members": [
                            {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "project": "project",
                                                "filter": "string",
                                                "order": "string"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": "none"
                            },
                            {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    "maxLength": 50
                },
                "id": "4736234238975447"
            },
            {
                "name": "file-table",
                "inputs": {
                    "file": 22
                }
            },
            {
                "nodeType": "output",
                "fromOp": 23,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "entityName": "string",
                                "projectName": "string"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project",
                                "filter": "string",
                                "order": "string"
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "run": "run"
                                }
                            },
                            "value": {
                                "type": "union",
                                "members": [
                                    "none",
                                    {
                                        "type": "file",
                                        "extension": "json",
                                        "wbObjectType": {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    }
                                ]
                            }
                        },
                        "maxLength": 50
                    }
                },
                "id": "5916645818495800"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 24,
                    "key": 37
                }
            },
            {
                "nodeType": "output",
                "fromOp": 25,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "entityName": "string",
                                "projectName": "string"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project",
                                "filter": "string",
                                "order": "string"
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "run": "run"
                                }
                            },
                            "value": {
                                "type": "union",
                                "members": [
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_runtime": "number",
                                            "test_acc": "number",
                                            "_timestamp": "number",
                                            "evaluation": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "_step": "number",
                                            "_wandb": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "runtime": "number"
                                                }
                                            },
                                            "loss": "none",
                                            "test_data": "none",
                                            "train_data": "none"
                                        }
                                    },
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_runtime": "number",
                                            "test_acc": "none",
                                            "_timestamp": "number",
                                            "evaluation": "none",
                                            "_step": "number",
                                            "_wandb": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "runtime": "number"
                                                }
                                            },
                                            "loss": "number",
                                            "test_data": "none",
                                            "train_data": "none"
                                        }
                                    },
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_runtime": "number",
                                            "test_acc": "none",
                                            "_timestamp": "number",
                                            "evaluation": "none",
                                            "_step": "number",
                                            "_wandb": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "runtime": "number"
                                                }
                                            },
                                            "loss": "none",
                                            "test_data": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "train_data": "none"
                                        }
                                    },
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_runtime": "number",
                                            "test_acc": "none",
                                            "_timestamp": "number",
                                            "evaluation": "none",
                                            "_step": "number",
                                            "_wandb": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "runtime": "number"
                                                }
                                            },
                                            "loss": "none",
                                            "test_data": "none",
                                            "train_data": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        },
                        "maxLength": 50
                    }
                },
                "id": "5702048823281650"
            },
            {
                "name": "run-summary",
                "inputs": {
                    "run": 26
                }
            },
            {
                "nodeType": "output",
                "fromOp": 27,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "entityName": "string",
                                "projectName": "string"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project",
                                "filter": "string",
                                "order": "string"
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": "run",
                        "maxLength": 50
                    }
                },
                "id": "5780701654745467"
            },
            {
                "name": "limit",
                "inputs": {
                    "arr": 28,
                    "limit": 36
                }
            },
            {
                "nodeType": "output",
                "fromOp": 29,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "entityName": "string",
                                "projectName": "string"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project",
                                "filter": "string",
                                "order": "string"
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": "run"
                    }
                },
                "id": "8782079909618368"
            },
            {
                "name": "project-filteredRuns",
                "inputs": {
                    "project": 30,
                    "filter": 34,
                    "order": 35
                }
            },
            {
                "nodeType": "output",
                "fromOp": 31,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "entityName": "string",
                            "projectName": "string"
                        }
                    },
                    "value": "project"
                },
                "id": "2213153157664977"
            },
            {
                "name": "root-project",
                "inputs": {
                    "entityName": 32,
                    "projectName": 33
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "stacey"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "weaveform"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "{\"name\":{\"$ne\":null}}"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "-createdAt"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 50
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "train_data"
            },
            {
                "nodeType": "const",
                "type": {
                    "type": "function",
                    "inputTypes": {
                        "row": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "indexCheckpoint": "number"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    },
                    "outputType": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "union",
                                "members": [
                                    {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "entityName": "string",
                                                        "projectName": "string"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project",
                                                        "filter": "string",
                                                        "order": "string"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "run": "run"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "file": {
                                                    "type": "file",
                                                    "extension": "json",
                                                    "wbObjectType": {
                                                        "type": "table",
                                                        "columnTypes": {}
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    }
                                ]
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "table": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            {
                                                "type": "table",
                                                "columnTypes": {}
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "value": {
                            "type": "union",
                            "members": [
                                "none",
                                "boolean"
                            ]
                        }
                    }
                },
                "val": {
                    "nodeType": "output",
                    "fromOp": 40
                }
            },
            {
                "nodeType": "output",
                "fromOp": 40,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "union",
                            "members": [
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "project": "project",
                                                "filter": "string",
                                                "order": "string"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                }
                            ]
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "table": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "boolean"
                        ]
                    }
                },
                "id": "3506108838912478"
            },
            {
                "name": "or",
                "inputs": {
                    "lhs": 41,
                    "rhs": 48
                }
            },
            {
                "nodeType": "output",
                "fromOp": 42,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "union",
                            "members": [
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "project": "project",
                                                "filter": "string",
                                                "order": "string"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                }
                            ]
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "table": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "boolean"
                        ]
                    }
                },
                "id": "8869075488075259"
            },
            {
                "name": "number-greater",
                "inputs": {
                    "lhs": 43,
                    "rhs": 47
                }
            },
            {
                "nodeType": "output",
                "fromOp": 44,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "union",
                            "members": [
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "project": "project",
                                                "filter": "string",
                                                "order": "string"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                }
                            ]
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "table": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "number"
                        ]
                    }
                },
                "id": "5679787056691491"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 45,
                    "key": 46
                }
            },
            {
                "nodeType": "var",
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "union",
                            "members": [
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "project": "project",
                                                "filter": "string",
                                                "order": "string"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                }
                            ]
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "table": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "img": {
                                "type": "union",
                                "members": [
                                    "none",
                                    {
                                        "type": "image-file",
                                        "boxLayers": {},
                                        "boxScoreKeys": [],
                                        "maskLayers": {},
                                        "classMap": {}
                                    }
                                ]
                            },
                            "label": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            }
                        }
                    }
                },
                "varName": "row"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 4
            },
            {
                "nodeType": "output",
                "fromOp": 49,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "union",
                            "members": [
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "project": "project",
                                                "filter": "string",
                                                "order": "string"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                }
                            ]
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "table": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "boolean"
                        ]
                    }
                },
                "id": "45985813183469"
            },
            {
                "name": "number-equal",
                "inputs": {
                    "lhs": 50,
                    "rhs": 54
                }
            },
            {
                "nodeType": "output",
                "fromOp": 51,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "union",
                            "members": [
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "project": "project",
                                                "filter": "string",
                                                "order": "string"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                }
                            ]
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "table": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "number"
                        ]
                    }
                },
                "id": "5679787056691491"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 52,
                    "key": 53
                }
            },
            {
                "nodeType": "var",
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "union",
                            "members": [
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string"
                                                }
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    }
                                },
                                {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "project": "project",
                                                "filter": "string",
                                                "order": "string"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                }
                            ]
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "table": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    ]
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "img": {
                                "type": "union",
                                "members": [
                                    "none",
                                    {
                                        "type": "image-file",
                                        "boxLayers": {},
                                        "boxScoreKeys": [],
                                        "maskLayers": {},
                                        "classMap": {}
                                    }
                                ]
                            },
                            "label": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            }
                        }
                    }
                },
                "varName": "row"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 0
            },
            {
                "nodeType": "const",
                "type": {
                    "type": "function",
                    "inputTypes": {
                        "row": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "indexCheckpoint": "number"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    },
                    "outputType": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "val": {
                    "nodeType": "output",
                    "fromOp": 57
                }
            },
            {
                "nodeType": "output",
                "fromOp": 57,
                "type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "label": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            }
                        }
                    }
                },
                "id": "7887331919588768"
            },
            {
                "name": "dict",
                "inputs": {
                    "label": 58
                }
            },
            {
                "nodeType": "output",
                "fromOp": 59,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "3008109668814448"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 60,
                    "key": 61
                }
            },
            {
                "nodeType": "var",
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "img": {
                                "type": "union",
                                "members": [
                                    {
                                        "type": "image-file",
                                        "_is_object": True,
                                        "path": {
                                            "type": "ArtifactEntry"
                                        },
                                        "format": "string",
                                        "height": "int",
                                        "width": "int",
                                        "sha256": "string"
                                    },
                                    "none"
                                ]
                            },
                            "label": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            }
                        }
                    }
                },
                "varName": "row"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "const",
                "type": {
                    "type": "function",
                    "inputTypes": {
                        "row": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "groupKey": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "label": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "tagged",
                                                        "tag": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "project": "project"
                                                            }
                                                        },
                                                        "value": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "run": "run"
                                                            }
                                                        }
                                                    },
                                                    "value": {
                                                        "type": "union",
                                                        "members": [
                                                            "none",
                                                            "float"
                                                        ]
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "value": {
                                "type": "list",
                                "objectType": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "indexCheckpoint": "number"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "img": {
                                                "type": "union",
                                                "members": [
                                                    {
                                                        "type": "image-file",
                                                        "_is_object": True,
                                                        "path": {
                                                            "type": "ArtifactEntry"
                                                        },
                                                        "format": "string",
                                                        "height": "int",
                                                        "width": "int",
                                                        "sha256": "string"
                                                    },
                                                    "none"
                                                ]
                                            },
                                            "label": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "outputType": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            }
                        },
                        "minLength": 1,
                        "maxLength": 1
                    }
                },
                "val": {
                    "nodeType": "output",
                    "fromOp": 64
                }
            },
            {
                "nodeType": "output",
                "fromOp": 64,
                "type": {
                    "type": "list",
                    "objectType": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "run": "run"
                                }
                            }
                        },
                        "value": {
                            "type": "union",
                            "members": [
                                "none",
                                "float"
                            ]
                        }
                    },
                    "minLength": 1,
                    "maxLength": 1
                },
                "id": "8911313115366574"
            },
            {
                "name": "list",
                "inputs": {
                    "col-1dg91da9z": 65
                }
            },
            {
                "nodeType": "output",
                "fromOp": 66,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "7709346395915689"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 67,
                    "key": 70
                }
            },
            {
                "nodeType": "output",
                "fromOp": 68,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "id": "1448072007538299"
            },
            {
                "name": "group-groupkey",
                "inputs": {
                    "obj": 69
                }
            },
            {
                "nodeType": "var",
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "groupKey": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "label": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "run": "run"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "varName": "row"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "const",
                "type": {
                    "type": "list",
                    "objectType": "string"
                },
                "val": [
                    "asc"
                ]
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 0
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "output",
                "fromOp": 75,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "884811915755865"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 76,
                    "key": 81
                }
            },
            {
                "nodeType": "output",
                "fromOp": 77,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "id": "5245750396999690"
            },
            {
                "name": "group-groupkey",
                "inputs": {
                    "obj": 78
                }
            },
            {
                "nodeType": "output",
                "fromOp": 79,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "groupKey": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "label": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "run": "run"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "2944201576162417"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 6,
                    "index": 80
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 1
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "output",
                "fromOp": 83,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "4084508976837973"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 84,
                    "key": 89
                }
            },
            {
                "nodeType": "output",
                "fromOp": 85,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "id": "5330208441886616"
            },
            {
                "name": "group-groupkey",
                "inputs": {
                    "obj": 86
                }
            },
            {
                "nodeType": "output",
                "fromOp": 87,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "groupKey": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "label": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "run": "run"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "6137833366104300"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 6,
                    "index": 88
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 2
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "output",
                "fromOp": 91,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "5111736233100585"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 92,
                    "key": 97
                }
            },
            {
                "nodeType": "output",
                "fromOp": 93,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "id": "1265357254761960"
            },
            {
                "name": "group-groupkey",
                "inputs": {
                    "obj": 94
                }
            },
            {
                "nodeType": "output",
                "fromOp": 95,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "groupKey": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "label": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "run": "run"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "8407889158310100"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 6,
                    "index": 96
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 3
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "output",
                "fromOp": 99,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "1628325756114698"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 100,
                    "key": 105
                }
            },
            {
                "nodeType": "output",
                "fromOp": 101,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "id": "2508624089859093"
            },
            {
                "name": "group-groupkey",
                "inputs": {
                    "obj": 102
                }
            },
            {
                "nodeType": "output",
                "fromOp": 103,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "groupKey": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "label": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "run": "run"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "2372794278895355"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 6,
                    "index": 104
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 4
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "output",
                "fromOp": 107,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "2217308322536344"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 108,
                    "key": 113
                }
            },
            {
                "nodeType": "output",
                "fromOp": 109,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "id": "5945284620580839"
            },
            {
                "name": "group-groupkey",
                "inputs": {
                    "obj": 110
                }
            },
            {
                "nodeType": "output",
                "fromOp": 111,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "groupKey": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "label": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "run": "run"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "7606746469857612"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 6,
                    "index": 112
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 5
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "output",
                "fromOp": 115,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project"
                                }
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "run": "run"
                            }
                        }
                    },
                    "value": {
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "7299791020204116"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 116,
                    "key": 121
                }
            },
            {
                "nodeType": "output",
                "fromOp": 117,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "id": "3253557441045502"
            },
            {
                "name": "group-groupkey",
                "inputs": {
                    "obj": 118
                }
            },
            {
                "nodeType": "output",
                "fromOp": 119,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "groupKey": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "label": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    }
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "run": "run"
                                                    }
                                                }
                                            },
                                            "value": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "2303673815305339"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 6,
                    "index": 120
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 6
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "label"
            },
            {
                "nodeType": "output",
                "fromOp": 123,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": "number"
                },
                "id": "3272134082459489"
            },
            {
                "name": "count",
                "inputs": {
                    "arr": 6
                }
            },
            {
                "nodeType": "output",
                "fromOp": 125,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": "number"
                },
                "id": "3314238558707208"
            },
            {
                "name": "count",
                "inputs": {
                    "arr": 126
                }
            },
            {
                "nodeType": "output",
                "fromOp": 127,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "groupKey": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "label": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "project": "project"
                                                        }
                                                    },
                                                    "value": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "run": "run"
                                                        }
                                                    }
                                                },
                                                "value": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        "float"
                                                    ]
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "value": {
                                "type": "list",
                                "objectType": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "indexCheckpoint": "number"
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "run": "run"
                                            }
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "img": {
                                                "type": "union",
                                                "members": [
                                                    {
                                                        "type": "image-file",
                                                        "_is_object": True,
                                                        "path": {
                                                            "type": "ArtifactEntry"
                                                        },
                                                        "format": "string",
                                                        "height": "int",
                                                        "width": "int",
                                                        "sha256": "string"
                                                    },
                                                    "none"
                                                ]
                                            },
                                            "label": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    "float"
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "172866124020819"
            },
            {
                "name": "groupby",
                "inputs": {
                    "arr": 128,
                    "groupByFn": 130
                }
            },
            {
                "nodeType": "output",
                "fromOp": 129,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
                        }
                    },
                    "value": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "indexCheckpoint": "number"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                "id": "5427644232586845"
            },
            {
                "name": "list-createIndexCheckpointTag",
                "inputs": {
                    "arr": 14
                }
            },
            {
                "nodeType": "const",
                "type": {
                    "type": "function",
                    "inputTypes": {
                        "row": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "indexCheckpoint": "number"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "img": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "image-file",
                                                "_is_object": True,
                                                "path": {
                                                    "type": "ArtifactEntry"
                                                },
                                                "format": "string",
                                                "height": "int",
                                                "width": "int",
                                                "sha256": "string"
                                            },
                                            "none"
                                        ]
                                    },
                                    "label": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    }
                                }
                            }
                        }
                    },
                    "outputType": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "label": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "project": "project"
                                        }
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "run": "run"
                                        }
                                    }
                                },
                                "value": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                }
                            }
                        }
                    }
                },
                "val": {
                    "nodeType": "output",
                    "fromOp": 132
                }
            },
            {
                "nodeType": "output",
                "fromOp": 132,
                "type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "label": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project"
                                    }
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "run": "run"
                                    }
                                }
                            },
                            "value": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            }
                        }
                    }
                },
                "id": "7887331919588768"
            },
            {
                "name": "dict",
                "inputs": {
                    "label": 58
                }
            }
        ],
        "rootNodes": [
            # 0,
            # 74,
            # 82,
            # 90,
            # 98,
            # 106,
            114,
            # 122,
            124
        ]
    }
}
]
