from weave.server import _handle_request


def test_playback():
    for payload in execute_payloads:
        res = _handle_request(payload, True)
        assert "err" not in res


# Paste graphs below (from DD or Network tab to test)
execute_payloads: list[dict] = [{
    "graphs": {
        "nodes": [
            {
                "nodeType": "output",
                "fromOp": 1,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        "string"
                    ]
                },
                "id": "5247167031791451"
            },
            {
                "name": "file-directUrlAsOf",
                "inputs": {
                    "file": 2,
                    "asOf": 39
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
                            "type": "file"
                        }
                    ]
                },
                "id": "1013314854383808"
            },
            {
                "name": "artifactVersion-file",
                "inputs": {
                    "artifactVersion": 4,
                    "path": 38
                }
            },
            {
                "nodeType": "output",
                "fromOp": 5,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        "artifactVersion"
                    ]
                },
                "id": "3032789302251217"
            },
            {
                "name": "asset-artifactVersion",
                "inputs": {
                    "asset": 6
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
                        "type": "image-file",
                        "boxLayers": {},
                        "boxScoreKeys": [],
                        "maskLayers": {},
                        "classMap": {}
                    }
                },
                "id": "5636480037509130"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 8,
                    "key": 37
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
                            "row_num": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            },
                            "image": {
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
                            }
                        }
                    }
                },
                "id": "234435314405536"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 10,
                    "index": 36
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
                                "row_num": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                },
                                "image": {
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
                                }
                            }
                        }
                    },
                    "minLength": 0
                },
                "id": "5571333664506226"
            },
            {
                "name": "list-createIndexCheckpointTag",
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
                                "row_num": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        "number"
                                    ]
                                },
                                "image": {
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
                                }
                            }
                        }
                    },
                    "minLength": 0
                },
                "id": "4953888578829630"
            },
            {
                "name": "concat",
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
                                    "row_num": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
                                    },
                                    "image": {
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
                                    }
                                }
                            }
                        },
                        "minLength": 0
                    },
                    "minLength": 1,
                    "maxLength": 1
                },
                "id": "2489334804587106"
            },
            {
                "name": "dropna",
                "inputs": {
                    "arr": 16
                }
            },
            {
                "nodeType": "output",
                "fromOp": 17,
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
                                    "row_num": {
                                        "type": "union",
                                        "members": [
                                            "none",
                                            "number"
                                        ]
                                    },
                                    "image": {
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
                                    }
                                }
                            }
                        }
                    },
                    "minLength": 1,
                    "maxLength": 1
                },
                "id": "2028423970989221"
            },
            {
                "name": "table-rows",
                "inputs": {
                    "table": 18
                }
            },
            {
                "nodeType": "output",
                "fromOp": 19,
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
                "id": "2866193294821427"
            },
            {
                "name": "file-table",
                "inputs": {
                    "file": 20
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
                "id": "439092501232976"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 22,
                    "key": 35
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
                                    "table_with_images": {
                                        "type": "file",
                                        "extension": "json",
                                        "wbObjectType": {
                                            "type": "table",
                                            "columnTypes": {}
                                        }
                                    },
                                    "_step": "number"
                                }
                            }
                        },
                        "maxLength": 1
                    }
                },
                "id": "3790623923876197"
            },
            {
                "name": "run-summary",
                "inputs": {
                    "run": 24
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
                        "objectType": "run",
                        "maxLength": 1
                    }
                },
                "id": "8820415952460279"
            },
            {
                "name": "limit",
                "inputs": {
                    "arr": 26,
                    "limit": 34
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
                        "objectType": "run"
                    }
                },
                "id": "1312664955443068"
            },
            {
                "name": "project-filteredRuns",
                "inputs": {
                    "project": 28,
                    "filter": 32,
                    "order": 33
                }
            },
            {
                "nodeType": "output",
                "fromOp": 29,
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
                    "entityName": 30,
                    "projectName": 31
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
                "val": "{\"name\":\"2ylpne7v\"}"
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
                "val": "table_with_images"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 14
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "image"
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "media/images/4aa597e8916721318fc6.png"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 1668441446620
            },
            {
                "nodeType": "output",
                "fromOp": 41,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        "string"
                    ]
                },
                "id": "441075143619817"
            },
            {
                "name": "file-directUrlAsOf",
                "inputs": {
                    "file": 42,
                    "asOf": 52
                }
            },
            {
                "nodeType": "output",
                "fromOp": 43,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        {
                            "type": "file"
                        }
                    ]
                },
                "id": "1856744502136354"
            },
            {
                "name": "artifactVersion-file",
                "inputs": {
                    "artifactVersion": 44,
                    "path": 51
                }
            },
            {
                "nodeType": "output",
                "fromOp": 45,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        "artifactVersion"
                    ]
                },
                "id": "2452578571395669"
            },
            {
                "name": "asset-artifactVersion",
                "inputs": {
                    "asset": 46
                }
            },
            {
                "nodeType": "output",
                "fromOp": 47,
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
                        "type": "image-file",
                        "boxLayers": {},
                        "boxScoreKeys": [],
                        "maskLayers": {},
                        "classMap": {}
                    }
                },
                "id": "475191016216884"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 48,
                    "key": 37
                }
            },
            {
                "nodeType": "output",
                "fromOp": 49,
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
                            "row_num": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            },
                            "image": {
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
                            }
                        }
                    }
                },
                "id": "3127502921458054"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 10,
                    "index": 50
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 15
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "media/images/1f7d252ade8bcaa34d44.png"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 1668441446625
            },
            {
                "nodeType": "output",
                "fromOp": 54,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        "string"
                    ]
                },
                "id": "4538416721386524"
            },
            {
                "name": "file-directUrlAsOf",
                "inputs": {
                    "file": 55,
                    "asOf": 65
                }
            },
            {
                "nodeType": "output",
                "fromOp": 56,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        {
                            "type": "file"
                        }
                    ]
                },
                "id": "5382998219716184"
            },
            {
                "name": "artifactVersion-file",
                "inputs": {
                    "artifactVersion": 57,
                    "path": 64
                }
            },
            {
                "nodeType": "output",
                "fromOp": 58,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        "artifactVersion"
                    ]
                },
                "id": "5144589458531910"
            },
            {
                "name": "asset-artifactVersion",
                "inputs": {
                    "asset": 59
                }
            },
            {
                "nodeType": "output",
                "fromOp": 60,
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
                        "type": "image-file",
                        "boxLayers": {},
                        "boxScoreKeys": [],
                        "maskLayers": {},
                        "classMap": {}
                    }
                },
                "id": "8508104437153204"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 61,
                    "key": 37
                }
            },
            {
                "nodeType": "output",
                "fromOp": 62,
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
                            "row_num": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            },
                            "image": {
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
                            }
                        }
                    }
                },
                "id": "7114809801232323"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 10,
                    "index": 63
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 16
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "media/images/5b2cb21f77f08af722af.png"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 1668441446626
            },
            {
                "nodeType": "output",
                "fromOp": 67,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        "string"
                    ]
                },
                "id": "3897558665476693"
            },
            {
                "name": "file-directUrlAsOf",
                "inputs": {
                    "file": 68,
                    "asOf": 78
                }
            },
            {
                "nodeType": "output",
                "fromOp": 69,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        {
                            "type": "file"
                        }
                    ]
                },
                "id": "5620494452569414"
            },
            {
                "name": "artifactVersion-file",
                "inputs": {
                    "artifactVersion": 70,
                    "path": 77
                }
            },
            {
                "nodeType": "output",
                "fromOp": 71,
                "type": {
                    "type": "union",
                    "members": [
                        "none",
                        "artifactVersion"
                    ]
                },
                "id": "4283364421995057"
            },
            {
                "name": "asset-artifactVersion",
                "inputs": {
                    "asset": 72
                }
            },
            {
                "nodeType": "output",
                "fromOp": 73,
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
                        "type": "image-file",
                        "boxLayers": {},
                        "boxScoreKeys": [],
                        "maskLayers": {},
                        "classMap": {}
                    }
                },
                "id": "8363502556764693"
            },
            {
                "name": "pick",
                "inputs": {
                    "obj": 74,
                    "key": 37
                }
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
                            "row_num": {
                                "type": "union",
                                "members": [
                                    "none",
                                    "number"
                                ]
                            },
                            "image": {
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
                            }
                        }
                    }
                },
                "id": "7987801190104960"
            },
            {
                "name": "index",
                "inputs": {
                    "arr": 10,
                    "index": 76
                }
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 17
            },
            {
                "nodeType": "const",
                "type": "string",
                "val": "media/images/e0c40863c9eb0caf570e.png"
            },
            {
                "nodeType": "const",
                "type": "number",
                "val": 1668441446627
            }
        ],
        "rootNodes": [
            0,
            40,
            53,
            66
        ]
    }
}]
