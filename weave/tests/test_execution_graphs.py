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
                "id": "1644853512780086"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 51
                }
            },
            {
                "nodeType": "output",
                "fromOp": 3,
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
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
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
                            "numbers": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            },
                            "maybe_numbers": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            }
                        }
                    }
                },
                "id": "4415703862313380"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 4,
                    "index": 50
                }
            },
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
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
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
                                "numbers": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                },
                                "maybe_numbers": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                }
                            }
                        }
                    },
                    "minLength": 0
                },
                "id": "3939432258038251"
            },
            {
                "name": "sort",
                "inputs": {
                    "arr": 6,
                    "compFn": 42,
                    "columnDirs": 49
                }
            },
            {
                "nodeType": "output",
                "fromOp": 7,
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
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
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
                                "numbers": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                },
                                "maybe_numbers": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                }
                            }
                        }
                    },
                    "minLength": 0
                },
                "id": "3263053606645843"
            },
            {
                "name": "filter",
                "inputs": {
                    "arr": 8,
                    "filterFn": 34
                }
            },
            {
                "nodeType": "output",
                "fromOp": 9,
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
                                                }
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string"
                                                }
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
                                "numbers": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                },
                                "maybe_numbers": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                }
                            }
                        }
                    },
                    "minLength": 0
                },
                "id": "1258015020852933"
            },
            {
                "name": "list-createIndexCheckpointTag",
                "inputs": {
                    "arr": 10
                }
            },
            {
                "nodeType": "output",
                "fromOp": 11,
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
                                "numbers": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                },
                                "maybe_numbers": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                }
                            }
                        }
                    },
                    "minLength": 0
                },
                "id": "791154174751887"
            },
            {
                "name": "concat",
                "inputs": {
                    "arr": 12
                }
            },
            {
                "nodeType": "output",
                "fromOp": 13,
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
                                    "numbers": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
                                    },
                                    "maybe_numbers": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
                                    }
                                }
                            }
                        },
                        "minLength": 0
                    },
                    "minLength": 1,
                    "maxLength": 1
                },
                "id": "4188511802625854"
            },
            {
                "name": "dropna",
                "inputs": {
                    "arr": 14
                }
            },
            {
                "nodeType": "output",
                "fromOp": 15,
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
                                    "numbers": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
                                    },
                                    "maybe_numbers": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
                                    }
                                }
                            }
                        }
                    },
                    "minLength": 1,
                    "maxLength": 1
                },
                "id": "8389670565843922"
            },
            {
                "name": "table-rows",
                "inputs": {
                    "table": 16
                }
            },
            {
                "nodeType": "output",
                "fromOp": 17,
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
                    "maxLength": 1
                },
                "id": "5114474665798360"
            },
            {
                "name": "file-table",
                "inputs": {
                    "file": 18
                }
            },
            {
                "nodeType": "output",
                "fromOp": 19,
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
                        "maxLength": 1
                    }
                },
                "id": "3009629810035793"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 20,
                    "key": 33
                }
            },
            {
                "nodeType": "output",
                "fromOp": 21,
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
                                    "_step": "number",
                                    "table": {
                                        "type": "file",
                                        "extension": "json",
                                        "wbObjectType": {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    },
                                    "_wandb": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "runtime": "number"
                                        }
                                    },
                                    "_runtime": "number",
                                    "_timestamp": "number"
                                }
                            }
                        },
                        "maxLength": 1
                    }
                },
                "id": "3092865125033765"
            },
            {
                "name": "run-summary",
                "inputs": {
                    "run": 22
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
                        "objectType": "run",
                        "maxLength": 1
                    }
                },
                "id": "6638502797568267"
            },
            {
                "name": "limit",
                "inputs": {
                    "arr": 24,
                    "limit": 32
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
                        "objectType": "run"
                    }
                },
                "id": "1069660331113602"
            },
            {
                "name": "project-filteredRuns",
                "inputs": {
                    "project": 26,
                    "filter": 30,
                    "order": 31
                }
            },
            {
                "nodeType": "output",
                "fromOp": 27,
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
                    "entityName": 28,
                    "projectName": 29
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
                "val": "{\"name\":\"mcgtiax8\"}"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "+createdAt"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 1
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "table"
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
                                        "type": "tagged",
                                        "tag": {
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
                                                        "entityName": "string",
                                                        "projectName": "string"
                                                    }
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
                                    "numbers": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
                                    },
                                    "maybe_numbers": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
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
                    "fromOp": 36
                }
            },
            {
                "nodeType": "output",
                "fromOp": 36,
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
                "id": "3148851372782019"
            },
            {
                "name": "number-less",
                "inputs": {
                    "lhs": 37,
                    "rhs": 41
                }
            },
            {
                "nodeType": "output",
                "fromOp": 38,
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
                "id": "2421193481749747"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 39,
                    "key": 40
                }
            },
            {
                "nodeType": "var",
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
                            "numbers": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            },
                            "maybe_numbers": {
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
                "val": "maybe_numbers"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 3
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
                                        "type": "tagged",
                                        "tag": {
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
                                                        "entityName": "string",
                                                        "projectName": "string"
                                                    }
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
                                    "numbers": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
                                    },
                                    "maybe_numbers": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
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
                        "minLength": 1,
                        "maxLength": 1
                    }
                },
                "val": {
                    "nodeType": "output",
                    "fromOp": 44
                }
            },
            {
                "nodeType": "output",
                "fromOp": 44,
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
                    "minLength": 1,
                    "maxLength": 1
                },
                "id": "337076985484568"
            },
            {
                "name": "list",
                "inputs": {
                    "col-uogaju8ls": 45
                }
            },
            {
                "nodeType": "output",
                "fromOp": 46,
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
                "id": "5235476838078225"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 47,
                    "key": 48
                }
            },
            {
                "nodeType": "var",
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
                                            }
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string"
                                            }
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
                            "numbers": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            },
                            "maybe_numbers": {
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
                "val": "maybe_numbers"
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
                "val": "numbers"
            },
            {
                "nodeType": "output",
                "fromOp": 53,
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
                "id": "3665732246403308"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 48
                }
            }
        ],
        "rootNodes": [
            0,
            52
        ]
    }
}
]
