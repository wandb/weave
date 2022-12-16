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
                "type": "type",
                "id": "7858761845202675"
            },
            {
                "name": "table-rowsType",
                "inputs": {
                    "table": 2
                }
            },
            {
                "nodeType": "output",
                "fromOp": 3,
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
                    },
                    "maxLength": 50
                },
                "id": "5365197425635320"
            },
            {
                "name": "file-table",
                "inputs": {
                    "file": 4
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
                                "type": "file",
                                "extension": "json",
                                "wbObjectType": {
                                    "type": "table",
                                    "columnTypes": {}
                                }
                            }
                        },
                        "maxLength": 50
                    }
                },
                "id": "7220669708353818"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 6,
                    "key": 19
                }
            },
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
                                "type": "typedDict",
                                "propertyTypes": {
                                    "_runtime": "number",
                                    "_timestamp": "number",
                                    "small_table": {
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
                                    }
                                }
                            }
                        },
                        "maxLength": 50
                    }
                },
                "id": "6810117533994064"
            },
            {
                "name": "run-summary",
                "inputs": {
                    "run": 8
                }
            },
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
                "id": "7900566339215233"
            },
            {
                "name": "limit",
                "inputs": {
                    "arr": 10,
                    "limit": 18
                }
            },
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
                "id": "8908956892966953"
            },
            {
                "name": "project-filteredRuns",
                "inputs": {
                    "project": 12,
                    "filter": 16,
                    "order": 17
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
                            "entityName": "string",
                            "projectName": "string"
                        }
                    },
                    "value": "project"
                },
                "id": "1228024693382936"
            },
            {
                "name": "root-project",
                "inputs": {
                    "entityName": 14,
                    "projectName": 15
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "timssweeney"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "dev_public_tables"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "{\"$and\":[{\"name\":{\"$ne\":\"2ase1uju\"}},{\"name\":{\"$ne\":\"w9p60krw\"}}]}"
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
                "val": "small_table"
            }
        ],
        "rootNodes": [
            0
        ]
    }
}
]
