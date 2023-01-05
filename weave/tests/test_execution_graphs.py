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
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "8630347193355650"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 26
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
                            "c_0": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_1": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_2": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_3": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_4": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_5": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_6": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_7": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_8": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_9": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            }
                        }
                    }
                },
                "id": "2399125476539773"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 4,
                    "index": 25
                }
            },
            {
                "nodeType": "output",
                "fromOp": 5,
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
                                    "indexCheckpoint": "number"
                                }
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "c_0": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_1": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_2": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_3": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_4": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_5": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_6": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_7": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_8": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "float"
                                        ]
                                    },
                                    "c_9": {
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
                "id": "630608847645607"
            },
            {
                "name": "list-createIndexCheckpointTag",
                "inputs": {
                    "arr": 6
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
                        "type": "ArrowWeaveList",
                        "_base_type": {
                            "type": "list",
                            "objectType": "any"
                        },
                        "objectType": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "c_0": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_1": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_2": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_3": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_4": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_5": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_6": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_7": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_8": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "float"
                                    ]
                                },
                                "c_9": {
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
                "id": "3109621838065958"
            },
            {
                "name": "table-rows",
                "inputs": {
                    "table": 8
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
                                    "artifactName": "string"
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
                "id": "3318581910594429"
            },
            {
                "name": "file-table",
                "inputs": {
                    "file": 10
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
                                "artifactName": "string"
                            }
                        }
                    },
                    "value": {
                        "type": "file",
                        "extension": "json",
                        "wbObjectType": {
                            "type": "table"
                        }
                    }
                },
                "id": "4598168113739221"
            },
            {
                "name": "artifactVersion-file",
                "inputs": {
                    "artifactVersion": 12,
                    "path": 24
                }
            },
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
                                "projectName": "string"
                            }
                        },
                        "value": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "project": "project",
                                "artifactName": "string"
                            }
                        }
                    },
                    "value": "artifactVersion"
                },
                "id": "7906858553552428"
            },
            {
                "name": "artifactMembership-artifactVersion",
                "inputs": {
                    "artifactMembership": 14
                }
            },
            {
                "nodeType": "output",
                "fromOp": 15,
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
                                "artifactName": "string"
                            }
                        }
                    },
                    "value": "artifactMembership"
                },
                "id": "1919257416316310"
            },
            {
                "name": "artifact-membershipForAlias",
                "inputs": {
                    "artifact": 16,
                    "aliasName": 23
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
                                "artifactName": "string"
                            }
                        }
                    },
                    "value": "artifact"
                },
                "id": "7301150652433478"
            },
            {
                "name": "project-artifact",
                "inputs": {
                    "project": 18,
                    "artifactName": 22
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
                    "entityName": 20,
                    "projectName": 21
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
                "val": "run-2ase1uju-small_table_6"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "v0"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "small_table_6.table.json"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 0
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_0"
            },
            {
                "nodeType": "output",
                "fromOp": 28,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "5615080312048874"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 29
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_1"
            },
            {
                "nodeType": "output",
                "fromOp": 31,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "8323928211191881"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 32
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_2"
            },
            {
                "nodeType": "output",
                "fromOp": 34,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "3987371746666297"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 35
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_3"
            },
            {
                "nodeType": "output",
                "fromOp": 37,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6437414015552286"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 38
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_4"
            },
            {
                "nodeType": "output",
                "fromOp": 40,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6575464537605493"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 41
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_5"
            },
            {
                "nodeType": "output",
                "fromOp": 43,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "7647047388130580"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 44
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_6"
            },
            {
                "nodeType": "output",
                "fromOp": 46,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "4722884341607153"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 47
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_7"
            },
            {
                "nodeType": "output",
                "fromOp": 49,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6610951207601452"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 50
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_8"
            },
            {
                "nodeType": "output",
                "fromOp": 52,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "8237435895236899"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 2,
                    "key": 53
                }
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "c_9"
            },
            {
                "nodeType": "output",
                "fromOp": 55,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6463268040234319"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 26
                }
            },
            {
                "nodeType": "output",
                "fromOp": 57,
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
                                "indexCheckpoint": "number"
                            }
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "c_0": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_1": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_2": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_3": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_4": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_5": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_6": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_7": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_8": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_9": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            }
                        }
                    }
                },
                "id": "72147913552613"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 4,
                    "index": 58
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 1
            },
            {
                "nodeType": "output",
                "fromOp": 60,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "8349600728867924"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 29
                }
            },
            {
                "nodeType": "output",
                "fromOp": 62,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "80668188798011"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 32
                }
            },
            {
                "nodeType": "output",
                "fromOp": 64,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "8445676298588572"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 35
                }
            },
            {
                "nodeType": "output",
                "fromOp": 66,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "2705103304634323"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 38
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
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "1177841614414463"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 41
                }
            },
            {
                "nodeType": "output",
                "fromOp": 70,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "1662950665783565"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 44
                }
            },
            {
                "nodeType": "output",
                "fromOp": 72,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "2484801019240842"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 47
                }
            },
            {
                "nodeType": "output",
                "fromOp": 74,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "8854582884223685"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 50
                }
            },
            {
                "nodeType": "output",
                "fromOp": 76,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6633350685484432"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 56,
                    "key": 53
                }
            },
            {
                "nodeType": "output",
                "fromOp": 78,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6136466187254532"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 26
                }
            },
            {
                "nodeType": "output",
                "fromOp": 80,
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
                                "indexCheckpoint": "number"
                            }
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "c_0": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_1": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_2": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_3": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_4": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_5": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_6": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_7": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_8": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_9": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            }
                        }
                    }
                },
                "id": "2428925078801674"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 4,
                    "index": 81
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 2
            },
            {
                "nodeType": "output",
                "fromOp": 83,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6823972486876704"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 29
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
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "5433246649158548"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 32
                }
            },
            {
                "nodeType": "output",
                "fromOp": 87,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "3053558098946295"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 35
                }
            },
            {
                "nodeType": "output",
                "fromOp": 89,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "3542297208077731"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 38
                }
            },
            {
                "nodeType": "output",
                "fromOp": 91,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "7578089902524303"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 41
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
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "1085471975590465"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 44
                }
            },
            {
                "nodeType": "output",
                "fromOp": 95,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "1811748866607415"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 47
                }
            },
            {
                "nodeType": "output",
                "fromOp": 97,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "8361501492100815"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 50
                }
            },
            {
                "nodeType": "output",
                "fromOp": 99,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6164381041225120"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 79,
                    "key": 53
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
                        "type": "union",
                        "members": [
                            "none",
                            "float"
                        ]
                    }
                },
                "id": "661105218000379"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 26
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
                                "indexCheckpoint": "number"
                            }
                        }
                    },
                    "value": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "c_0": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_1": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_2": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_3": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_4": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_5": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_6": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_7": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_8": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            },
                            "c_9": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "float"
                                ]
                            }
                        }
                    }
                },
                "id": "8847344198363507"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 4,
                    "index": 104
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 3
            },
            {
                "nodeType": "output",
                "fromOp": 106,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "2643514727287558"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 29
                }
            },
            {
                "nodeType": "output",
                "fromOp": 108,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "2727651235094383"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 32
                }
            },
            {
                "nodeType": "output",
                "fromOp": 110,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "3952818315029339"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 35
                }
            },
            {
                "nodeType": "output",
                "fromOp": 112,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "5154298671339778"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 38
                }
            },
            {
                "nodeType": "output",
                "fromOp": 114,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "161246468164426"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 41
                }
            },
            {
                "nodeType": "output",
                "fromOp": 116,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "6392155465579244"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 44
                }
            },
            {
                "nodeType": "output",
                "fromOp": 118,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "8695014527076527"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 47
                }
            },
            {
                "nodeType": "output",
                "fromOp": 120,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "4482516767096762"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 50
                }
            },
            {
                "nodeType": "output",
                "fromOp": 122,
                "type": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": "project"
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
                "id": "4849292868960021"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 102,
                    "key": 53
                }
            }
        ],
        "rootNodes": [
            0,
            27,
            30,
            33,
            36,
            39,
            42,
            45,
            48,
            51,
            54,
            59,
            61,
            63,
            65,
            67,
            69,
            71,
            73,
            75,
            77,
            82,
            84,
            86,
            88,
            90,
            92,
            94,
            96,
            98,
            100,
            105,
            107,
            109,
            111,
            113,
            115,
            117,
            119,
            121
        ]
    }
}
]
