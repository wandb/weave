from weave.server import _handle_request


def test_playback():
    for payload in execute_payloads:
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
                    "type": "number",
                    "id": "6212437649555518",
                },
                {"name": "count", "inputs": {"arr": 2}},
                {
                    "nodeType": "output",
                    "fromOp": 3,
                    "type": {
                        "type": "list",
                        "objectType": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
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
                                                        "projectName": "string",
                                                    },
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    },
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"run": "run"},
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "file": {
                                                    "type": "file",
                                                    "extension": "json",
                                                    "wbObjectType": {
                                                        "type": "table",
                                                        "columnTypes": {},
                                                    },
                                                }
                                            },
                                        },
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
                                                        "columnTypes": {},
                                                    },
                                                ],
                                            }
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "c_0": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_1": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_2": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_3": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_4": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_5": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_6": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_7": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_8": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_9": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                    },
                                },
                            },
                        },
                        "minLength": 1,
                        "maxLength": 1,
                    },
                    "id": "1630237331649163",
                },
                {"name": "table-rows", "inputs": {"table": 4}},
                {
                    "nodeType": "output",
                    "fromOp": 5,
                    "type": {
                        "type": "list",
                        "objectType": {
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
                                                "projectName": "string",
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "file": {
                                            "type": "file",
                                            "extension": "json",
                                            "wbObjectType": {
                                                "type": "table",
                                                "columnTypes": {},
                                            },
                                        }
                                    },
                                },
                            },
                            "value": {
                                "type": "union",
                                "members": [
                                    "none",
                                    {"type": "table", "columnTypes": {}},
                                ],
                            },
                        },
                        "maxLength": 50,
                    },
                    "id": "7329444292374051",
                },
                {"name": "file-table", "inputs": {"file": 6}},
                {
                    "nodeType": "output",
                    "fromOp": 7,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"run": "run"},
                                },
                                "value": {
                                    "type": "file",
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "columnTypes": {},
                                    },
                                },
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "1525850803506243",
                },
                {"name": "pick", "inputs": {"obj": 8, "key": 19}},
                {
                    "nodeType": "output",
                    "fromOp": 9,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"run": "run"},
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "_step": "number",
                                        "_wandb": {
                                            "type": "typedDict",
                                            "propertyTypes": {"runtime": "number"},
                                        },
                                        "_runtime": "number",
                                        "_timestamp": "number",
                                        "small_table": {
                                            "type": "file",
                                            "extension": "json",
                                            "wbObjectType": {
                                                "type": "table",
                                                "columnTypes": {},
                                            },
                                        },
                                    },
                                },
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "3117230952567018",
                },
                {"name": "run-summary", "inputs": {"run": 10}},
                {
                    "nodeType": "output",
                    "fromOp": 11,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {"type": "list", "objectType": "run", "maxLength": 50},
                    },
                    "id": "5981012718708336",
                },
                {"name": "limit", "inputs": {"arr": 12, "limit": 18}},
                {
                    "nodeType": "output",
                    "fromOp": 13,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {"type": "list", "objectType": "run"},
                    },
                    "id": "8994115873573894",
                },
                {"name": "project-runs", "inputs": {"project": 14}},
                {
                    "nodeType": "output",
                    "fromOp": 15,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "entityName": "string",
                                "projectName": "string",
                            },
                        },
                        "value": "project",
                    },
                    "id": "1228024693382936",
                },
                {
                    "name": "root-project",
                    "inputs": {"entityName": 16, "projectName": 17},
                },
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "dev_public_tables"},
                {"nodeType": "const", "type": "number", "val": 50},
                {"nodeType": "const", "type": "string", "val": "small_table"},
                {
                    "nodeType": "output",
                    "fromOp": 21,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
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
                                                    "indexCheckpoint": "number"
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string",
                                                },
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "file": {
                                            "type": "file",
                                            "extension": "json",
                                            "wbObjectType": {
                                                "type": "table",
                                                "columnTypes": {},
                                            },
                                        }
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "table": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            {"type": "table", "columnTypes": {}},
                                        ],
                                    }
                                },
                            },
                        },
                        "value": {"type": "union", "members": ["none", "number"]},
                    },
                    "id": "4194391066173354",
                },
                {"name": "pick", "inputs": {"obj": 22, "key": 49}},
                {
                    "nodeType": "output",
                    "fromOp": 23,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
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
                                                    "indexCheckpoint": "number"
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string",
                                                },
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "file": {
                                            "type": "file",
                                            "extension": "json",
                                            "wbObjectType": {
                                                "type": "table",
                                                "columnTypes": {},
                                            },
                                        }
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "table": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            {"type": "table", "columnTypes": {}},
                                        ],
                                    }
                                },
                            },
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "c_0": {"type": "union", "members": ["none", "number"]},
                                "c_1": {"type": "union", "members": ["none", "number"]},
                                "c_2": {"type": "union", "members": ["none", "number"]},
                                "c_3": {"type": "union", "members": ["none", "number"]},
                                "c_4": {"type": "union", "members": ["none", "number"]},
                                "c_5": {"type": "union", "members": ["none", "number"]},
                                "c_6": {"type": "union", "members": ["none", "number"]},
                                "c_7": {"type": "union", "members": ["none", "number"]},
                                "c_8": {"type": "union", "members": ["none", "number"]},
                                "c_9": {"type": "union", "members": ["none", "number"]},
                            },
                        },
                    },
                    "id": "6053679686054153",
                },
                {"name": "index", "inputs": {"arr": 24, "index": 48}},
                {
                    "nodeType": "output",
                    "fromOp": 25,
                    "type": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
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
                                                        "indexCheckpoint": "number"
                                                    },
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "entityName": "string",
                                                        "projectName": "string",
                                                    },
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"project": "project"},
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"run": "run"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {},
                                                },
                                            }
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "table": {
                                            "type": "union",
                                            "members": [
                                                "none",
                                                {"type": "table", "columnTypes": {}},
                                            ],
                                        }
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "c_0": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_1": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_2": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_3": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_4": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_5": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_6": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_7": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_8": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_9": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                },
                            },
                        },
                        "minLength": 0,
                    },
                    "id": "2263396214129916",
                },
                {"name": "list-createIndexCheckpointTag", "inputs": {"arr": 26}},
                {
                    "nodeType": "output",
                    "fromOp": 27,
                    "type": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
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
                                                    "projectName": "string",
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"project": "project"},
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"run": "run"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "file": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {},
                                                },
                                            }
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "table": {
                                            "type": "union",
                                            "members": [
                                                "none",
                                                {"type": "table", "columnTypes": {}},
                                            ],
                                        }
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "c_0": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_1": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_2": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_3": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_4": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_5": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_6": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_7": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_8": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                    "c_9": {
                                        "type": "union",
                                        "members": ["none", "number"],
                                    },
                                },
                            },
                        },
                        "minLength": 0,
                    },
                    "id": "4960142109224228",
                },
                {"name": "concat", "inputs": {"arr": 28}},
                {
                    "nodeType": "output",
                    "fromOp": 29,
                    "type": {
                        "type": "list",
                        "objectType": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
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
                                                        "projectName": "string",
                                                    },
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    },
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"run": "run"},
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "file": {
                                                    "type": "file",
                                                    "extension": "json",
                                                    "wbObjectType": {
                                                        "type": "table",
                                                        "columnTypes": {},
                                                    },
                                                }
                                            },
                                        },
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
                                                        "columnTypes": {},
                                                    },
                                                ],
                                            }
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "c_0": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_1": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_2": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_3": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_4": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_5": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_6": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_7": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_8": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_9": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                    },
                                },
                            },
                            "minLength": 0,
                        },
                        "minLength": 1,
                        "maxLength": 1,
                    },
                    "id": "2016710112667302",
                },
                {"name": "dropna", "inputs": {"arr": 30}},
                {
                    "nodeType": "output",
                    "fromOp": 31,
                    "type": {
                        "type": "list",
                        "objectType": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
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
                                                        "projectName": "string",
                                                    },
                                                },
                                                "value": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    },
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"run": "run"},
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "file": {
                                                    "type": "file",
                                                    "extension": "json",
                                                    "wbObjectType": {
                                                        "type": "table",
                                                        "columnTypes": {},
                                                    },
                                                }
                                            },
                                        },
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
                                                        "columnTypes": {},
                                                    },
                                                ],
                                            }
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "c_0": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_1": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_2": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_3": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_4": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_5": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_6": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_7": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_8": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                        "c_9": {
                                            "type": "union",
                                            "members": ["none", "number"],
                                        },
                                    },
                                },
                            },
                        },
                        "minLength": 1,
                        "maxLength": 1,
                    },
                    "id": "1223762456011891",
                },
                {"name": "table-rows", "inputs": {"table": 32}},
                {
                    "nodeType": "output",
                    "fromOp": 33,
                    "type": {
                        "type": "list",
                        "objectType": {
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
                                                "projectName": "string",
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "file": {
                                            "type": "file",
                                            "extension": "json",
                                            "wbObjectType": {
                                                "type": "table",
                                                "columnTypes": {},
                                            },
                                        }
                                    },
                                },
                            },
                            "value": {
                                "type": "union",
                                "members": [
                                    "none",
                                    {"type": "table", "columnTypes": {}},
                                ],
                            },
                        },
                        "maxLength": 50,
                    },
                    "id": "6973031927749804",
                },
                {"name": "file-table", "inputs": {"file": 34}},
                {
                    "nodeType": "output",
                    "fromOp": 35,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"run": "run"},
                                },
                                "value": {
                                    "type": "file",
                                    "extension": "json",
                                    "wbObjectType": {
                                        "type": "table",
                                        "columnTypes": {},
                                    },
                                },
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "3472738659281700",
                },
                {"name": "pick", "inputs": {"obj": 36, "key": 47}},
                {
                    "nodeType": "output",
                    "fromOp": 37,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"run": "run"},
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "_wandb": {
                                            "type": "typedDict",
                                            "propertyTypes": {"runtime": "number"},
                                        },
                                        "_runtime": "number",
                                        "_timestamp": "number",
                                        "small_table": {
                                            "type": "file",
                                            "extension": "json",
                                            "wbObjectType": {
                                                "type": "table",
                                                "columnTypes": {},
                                            },
                                        },
                                        "_step": "number",
                                    },
                                },
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "7677153790943994",
                },
                {"name": "run-summary", "inputs": {"run": 38}},
                {
                    "nodeType": "output",
                    "fromOp": 39,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {"type": "list", "objectType": "run", "maxLength": 50},
                    },
                    "id": "5981012718708336",
                },
                {"name": "limit", "inputs": {"arr": 40, "limit": 46}},
                {
                    "nodeType": "output",
                    "fromOp": 41,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {"type": "list", "objectType": "run"},
                    },
                    "id": "8994115873573894",
                },
                {"name": "project-runs", "inputs": {"project": 42}},
                {
                    "nodeType": "output",
                    "fromOp": 43,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "entityName": "string",
                                "projectName": "string",
                            },
                        },
                        "value": "project",
                    },
                    "id": "1228024693382936",
                },
                {
                    "name": "root-project",
                    "inputs": {"entityName": 44, "projectName": 45},
                },
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "dev_public_tables"},
                {"nodeType": "const", "type": "number", "val": 50},
                {"nodeType": "const", "type": "string", "val": "small_table"},
                {"nodeType": "const", "type": "number", "val": 5},
                {"nodeType": "const", "type": "string", "val": "c_5"},
            ],
            "rootNodes": [0, 20],
        }
    }
]
