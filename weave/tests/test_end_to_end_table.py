import weave

# TODO: we need to actually execute the refine_output_type on dict pick before chaining the next op.
# Maybe we can just do this as the execute level and skip figuring this out at the dispatch level.
# yeah, because doung this correctly is going to require a significant refactor of the dispatch code.


# def test_end_to_end_query():
#     node = weave.ops.project("timssweeney", "keras_learning_rate")
#     node = node.filteredRuns('{"name":"4rbxec57"}', "+createdAt")
#     node = node.limit(1)
#     node = node.summary()
#     node = node["validation_predictions"]
#     node = node.table()
#     node = node.rows()
#     node = node.dropna()
#     node = node.concat()
#     node = node.createIndexCheckpointTag()
#     node = node[4]
#     node = node["output:max_class.label"]
#     assert weave.use(node) == "ship"

from weave.server import _handle_request


def test_end_to_end_execution():
    for payload in [requests[-1]]:
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
                    "id": "5006775084447754",
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
                    "id": "6021280798311683",
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
                    "id": "6576376696262289",
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
                    "id": "5979598482807720",
                },
                {"name": "root-project", "inputs": {"entityName": 8, "projectName": 9}},
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "keras_learning_rate"},
                {"nodeType": "const", "type": "string", "val": '{"name":{"$ne":null}}'},
                {"nodeType": "const", "type": "string", "val": "-createdAt"},
                {"nodeType": "const", "type": "number", "val": 50},
            ],
            "rootNodes": [0],
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
                    "id": "2377182998923253",
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
                                "value": "none",
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "3466349275246562",
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
                                "value": {"type": "typedDict", "propertyTypes": {}},
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "3536294956874416",
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
                    "id": "6021280798311683",
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
                    "id": "6576376696262289",
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
                    "id": "5979598482807720",
                },
                {
                    "name": "root-project",
                    "inputs": {"entityName": 12, "projectName": 13},
                },
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "keras_learning_rate"},
                {"nodeType": "const", "type": "string", "val": '{"name":{"$ne":null}}'},
                {"nodeType": "const", "type": "string", "val": "-createdAt"},
                {"nodeType": "const", "type": "number", "val": 50},
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "validation_predictions",
                },
            ],
            "rootNodes": [0],
        }
    },
    {
        "graphs": {
            "nodes": [
                {
                    "nodeType": "output",
                    "fromOp": 1,
                    "type": "type",
                    "id": "8672157828254704",
                },
                {"name": "table-rowsType", "inputs": {"table": 2}},
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
                                    "type": "typedDict",
                                    "propertyTypes": {"run": "run"},
                                },
                            },
                            "value": "none",
                        },
                        "maxLength": 50,
                    },
                    "id": "6599598770743241",
                },
                {"name": "file-table", "inputs": {"file": 4}},
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
                                "value": "none",
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "3466349275246562",
                },
                {"name": "pick", "inputs": {"obj": 6, "key": 19}},
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
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"run": "run"},
                                },
                                "value": {"type": "typedDict", "propertyTypes": {}},
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "3536294956874416",
                },
                {"name": "run-summary", "inputs": {"run": 8}},
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
                        "value": {"type": "list", "objectType": "run", "maxLength": 50},
                    },
                    "id": "6021280798311683",
                },
                {"name": "limit", "inputs": {"arr": 10, "limit": 18}},
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
                                "propertyTypes": {
                                    "project": "project",
                                    "filter": "string",
                                    "order": "string",
                                },
                            },
                        },
                        "value": {"type": "list", "objectType": "run"},
                    },
                    "id": "6576376696262289",
                },
                {
                    "name": "project-filteredRuns",
                    "inputs": {"project": 12, "filter": 16, "order": 17},
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
                                "projectName": "string",
                            },
                        },
                        "value": "project",
                    },
                    "id": "5979598482807720",
                },
                {
                    "name": "root-project",
                    "inputs": {"entityName": 14, "projectName": 15},
                },
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "keras_learning_rate"},
                {"nodeType": "const", "type": "string", "val": '{"name":{"$ne":null}}'},
                {"nodeType": "const", "type": "string", "val": "-createdAt"},
                {"nodeType": "const", "type": "number", "val": 50},
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "validation_predictions",
                },
            ],
            "rootNodes": [0],
        }
    },
]
