from weave.server import _handle_request


def test_end_to_end_execution():
    for payload in requests:
        res = _handle_request(payload, True)
        assert "error" not in res


requests = [
    {
        "graphs": {
            "nodes": [
                {
                    "nodeType": "output",
                    "fromOp": 1,
                    "type": "none",
                    "id": "8552742313501940",
                },
                {"name": "run-summary", "inputs": {"run": 2}},
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
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "filter": "string",
                                    "order": "string",
                                },
                            },
                        },
                        "value": {"type": "list", "objectType": "run", "maxLength": 50},
                    },
                    "id": "1235766920126375",
                },
                {"name": "limit", "inputs": {"arr": 4, "limit": 12}},
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
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "filter": "string",
                                    "order": "string",
                                },
                            },
                        },
                        "value": {"type": "list", "objectType": "run"},
                    },
                    "id": "2412107295658211",
                },
                {
                    "name": "project-filteredRuns",
                    "inputs": {"project": 6, "filter": 10, "order": 11},
                },
                {
                    "nodeType": "output",
                    "fromOp": 7,
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
                {"name": "root-project", "inputs": {"entityName": 8, "projectName": 9}},
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "dev_public_tables"},
                {"nodeType": "const", "type": "string", "val": '{"name":{"$ne":null}}'},
                {"nodeType": "const", "type": "string", "val": "-createdAt"},
                {"nodeType": "const", "type": "number", "val": 50},
                {
                    "nodeType": "output",
                    "fromOp": 14,
                    "type": "any",
                    "id": "5243905455708639",
                },
                {"name": "unioned_mapped_op-refine_summary_type", "inputs": {"run": 2}},
            ],
            "rootNodes": [0, 13],
        }
    },
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
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "filter": "string",
                                    "order": "string",
                                },
                            },
                        },
                        "value": "number",
                    },
                    "id": "4558698059995469",
                },
                {"name": "count", "inputs": {"arr": 2}},
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
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "filter": "string",
                                    "order": "string",
                                },
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
                                        "extension": "string",
                                        "wb_object_type": "string",
                                    },
                                },
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "425680889299573",
                },
                {"name": "pick", "inputs": {"obj": 4, "key": 17}},
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
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "filter": "string",
                                    "order": "string",
                                },
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
                                        "_runtime": "number",
                                        "_timestamp": "number",
                                        "small_table": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "extension": "string",
                                                "wb_object_type": "string",
                                            },
                                        },
                                        "_step": "number",
                                        "_wandb": {
                                            "type": "typedDict",
                                            "propertyTypes": {"runtime": "number"},
                                        },
                                    },
                                },
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "6908274470247985",
                },
                {"name": "run-summary", "inputs": {"run": 6}},
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
                                "propertyTypes": {
                                    "project": "project",
                                    "filter": "string",
                                    "order": "string",
                                },
                            },
                        },
                        "value": {"type": "list", "objectType": "run", "maxLength": 50},
                    },
                    "id": "1235766920126375",
                },
                {"name": "limit", "inputs": {"arr": 8, "limit": 16}},
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
                                "propertyTypes": {
                                    "project": "project",
                                    "filter": "string",
                                    "order": "string",
                                },
                            },
                        },
                        "value": {"type": "list", "objectType": "run"},
                    },
                    "id": "2412107295658211",
                },
                {
                    "name": "project-filteredRuns",
                    "inputs": {"project": 10, "filter": 14, "order": 15},
                },
                {
                    "nodeType": "output",
                    "fromOp": 11,
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
                    "inputs": {"entityName": 12, "projectName": 13},
                },
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "dev_public_tables"},
                {"nodeType": "const", "type": "string", "val": '{"name":{"$ne":null}}'},
                {"nodeType": "const", "type": "string", "val": "-createdAt"},
                {"nodeType": "const", "type": "number", "val": 50},
                {"nodeType": "const", "type": "string", "val": "small_table"},
            ],
            "rootNodes": [0],
        }
    },
]
