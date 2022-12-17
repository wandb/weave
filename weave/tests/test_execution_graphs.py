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
                    "type": "union",
                    "members": [
                        "none",
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
                            "value": "string"
                        }
                    ]
                },
                "id": "4180710155180848"
            },
            {
                "name": "run-name",
                "inputs": {
                    "run": 2
                }
            },
            {
                "nodeType": "output",
                "fromOp": 3,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        {
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
                            "value": "run"
                        }
                    ]
                },
                "id": "2352972880170948"
            },
            {
                "name": "tag-run",
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
                            "type": "union",
                            "members": [
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
                                {
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
                "id": "3196232769209286"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 6,
                    "index": 32
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
                                "type": "union",
                                "members": [
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
                                    {
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
                "id": "411500730641281"
            },
            {
                "name": "list-createIndexCheckpointTag",
                "inputs": {
                    "arr": 8
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
                "id": "6484295218339727"
            },
            {
                "name": "concat",
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
                        "type": "union",
                        "members": [
                            {
                                "type": "list",
                                "objectType": {
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
                            "none"
                        ]
                    },
                    "minLength": 6,
                    "maxLength": 6
                },
                "id": "7971222817359529"
            },
            {
                "name": "dropna",
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
                        "type": "union",
                        "members": [
                            {
                                "type": "list",
                                "objectType": {
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
                            "none"
                        ]
                    },
                    "minLength": 6,
                    "maxLength": 6
                },
                "id": "5346313308742289"
            },
            {
                "name": "table-rows",
                "inputs": {
                    "table": 14
                }
            },
            {
                "nodeType": "output",
                "fromOp": 15,
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
                            }
                        ]
                    },
                    "maxLength": 50
                },
                "id": "8480258618821666"
            },
            {
                "name": "file-table",
                "inputs": {
                    "file": 16
                }
            },
            {
                "nodeType": "output",
                "fromOp": 17,
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
                                        "type": "file",
                                        "extension": "json",
                                        "wbObjectType": {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    },
                                    "none"
                                ]
                            }
                        },
                        "maxLength": 50
                    }
                },
                "id": "4132555019204175"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 18,
                    "key": 31
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
                                "type": "union",
                                "members": [
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_wandb": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "runtime": "number"
                                                }
                                            },
                                            "_runtime": "number",
                                            "_timestamp": "number",
                                            "_step": "number",
                                            "table": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "small_table_3": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "small_table_6": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "small_table_8": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "small_table_9": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "_timestamp": "number",
                                            "small_table_0": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "small_table_1": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "small_table_5": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "small_table_2": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "small_table_4": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "small_table_7": {
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
                                            "_runtime": "number"
                                        }
                                    },
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_timestamp": "number",
                                            "small_table": {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {}
                                                }
                                            },
                                            "table_with_images": {
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
                                            "_runtime": "number"
                                        }
                                    },
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
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
                                            },
                                            "_runtime": "number"
                                        }
                                    }
                                ]
                            }
                        },
                        "maxLength": 50
                    }
                },
                "id": "8900511461584809"
            },
            {
                "name": "run-summary",
                "inputs": {
                    "run": 20
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
                        "objectType": "run",
                        "maxLength": 50
                    }
                },
                "id": "1235766920126375"
            },
            {
                "name": "limit",
                "inputs": {
                    "arr": 22,
                    "limit": 30
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
                        "objectType": "run"
                    }
                },
                "id": "2412107295658211"
            },
            {
                "name": "project-filteredRuns",
                "inputs": {
                    "project": 24,
                    "filter": 28,
                    "order": 29
                }
            },
            {
                "nodeType": "output",
                "fromOp": 25,
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
                    "entityName": 26,
                    "projectName": 27
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
                "val": "table"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 0
            },
            {
                "nodeType": "output",
                "fromOp": 34,
                "type": "number",
                "id": "935336375420740"
            },
            {
                "name": "tag-indexCheckpoint",
                "inputs": {
                    "obj": 4
                }
            },
            {
                "nodeType": "output",
                "fromOp": 36,
                "type": "number",
                "id": "5089940912529840"
            },
            {
                "name": "count",
                "inputs": {
                    "arr": 6
                }
            }
        ],
        "rootNodes": [
            0,
            33,
            35
        ]
    }
}
]
