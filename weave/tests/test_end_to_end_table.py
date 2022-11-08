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
                        "value": "number",
                    },
                    "id": "8440744431864711",
                },
                {"name": "pick", "inputs": {"obj": 2, "key": 18}},
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
                                    "propertyTypes": {"indexCheckpoint": "number"},
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
                                "_step": "number",
                                "_wandb": {
                                    "type": "typedDict",
                                    "propertyTypes": {"runtime": "number"},
                                },
                                "_runtime": "number",
                                "_timestamp": "number",
                                "small_table": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "extension": "string",
                                        "wb_object_type": "string",
                                        "path": "string",
                                    },
                                },
                            },
                        },
                    },
                    "id": "5357426932359037",
                },
                {"name": "index", "inputs": {"arr": 4, "index": 17}},
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
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"indexCheckpoint": "number"},
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
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
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "extension": "string",
                                                "wb_object_type": "string",
                                                "path": "string",
                                            },
                                        },
                                    },
                                },
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "501776913335480",
                },
                {"name": "list-createIndexCheckpointTag", "inputs": {"arr": 6}},
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
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "extension": "string",
                                                "wb_object_type": "string",
                                                "path": "string",
                                            },
                                        },
                                    },
                                },
                            },
                            "maxLength": 50,
                        },
                    },
                    "id": "1222751260716459",
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
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {"type": "list", "objectType": "run", "maxLength": 50},
                    },
                    "id": "5981012718708336",
                },
                {"name": "limit", "inputs": {"arr": 10, "limit": 16}},
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
                        "value": {"type": "list", "objectType": "run"},
                    },
                    "id": "8994115873573894",
                },
                {"name": "project-runs", "inputs": {"project": 12}},
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
                    "id": "1228024693382936",
                },
                {
                    "name": "root-project",
                    "inputs": {"entityName": 14, "projectName": 15},
                },
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "dev_public_tables"},
                {"nodeType": "const", "type": "number", "val": 50},
                {"nodeType": "const", "type": "number", "val": 0},
                {"nodeType": "const", "type": "string", "val": "_step"},
                {
                    "nodeType": "output",
                    "fromOp": 20,
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
                        "value": "number",
                    },
                    "id": "3064574234754890",
                },
                {"name": "pick", "inputs": {"obj": 2, "key": 21}},
                {"nodeType": "const", "type": "string", "val": "_wandb.runtime"},
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
                        "value": "number",
                    },
                    "id": "7742086078117385",
                },
                {"name": "pick", "inputs": {"obj": 2, "key": 24}},
                {"nodeType": "const", "type": "string", "val": "_runtime"},
                {
                    "nodeType": "output",
                    "fromOp": 26,
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
                        "value": "number",
                    },
                    "id": "383888362840766",
                },
                {"name": "pick", "inputs": {"obj": 2, "key": 27}},
                {"nodeType": "const", "type": "string", "val": "_timestamp"},
                {
                    "nodeType": "output",
                    "fromOp": 29,
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
                        "value": "string",
                    },
                    "id": "8319498460713860",
                },
                {"name": "pick", "inputs": {"obj": 2, "key": 30}},
                {"nodeType": "const", "type": "string", "val": "small_table.extension"},
                {
                    "nodeType": "output",
                    "fromOp": 32,
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
                        "value": "string",
                    },
                    "id": "7524627178403984",
                },
                {"name": "pick", "inputs": {"obj": 2, "key": 33}},
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "small_table.wb_object_type",
                },
                {
                    "nodeType": "output",
                    "fromOp": 35,
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
                        "value": "string",
                    },
                    "id": "7974388668451134",
                },
                {"name": "pick", "inputs": {"obj": 2, "key": 36}},
                {"nodeType": "const", "type": "string", "val": "small_table.path"},
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
                        "value": "number",
                    },
                    "id": "3553835936526396",
                },
                {"name": "pick", "inputs": {"obj": 39, "key": 18}},
                {
                    "nodeType": "output",
                    "fromOp": 40,
                    "type": {
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
                                    "propertyTypes": {"indexCheckpoint": "number"},
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
                                "_step": "number",
                                "_wandb": {
                                    "type": "typedDict",
                                    "propertyTypes": {"runtime": "number"},
                                },
                                "_runtime": "number",
                                "_timestamp": "number",
                                "small_table": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "extension": "string",
                                        "wb_object_type": "string",
                                        "path": "string",
                                    },
                                },
                            },
                        },
                    },
                    "id": "5818192002423605",
                },
                {"name": "index", "inputs": {"arr": 4, "index": 41}},
                {"nodeType": "const", "type": "number", "val": 1},
                {
                    "nodeType": "output",
                    "fromOp": 43,
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
                        "value": "number",
                    },
                    "id": "2822627119276657",
                },
                {"name": "pick", "inputs": {"obj": 39, "key": 21}},
                {
                    "nodeType": "output",
                    "fromOp": 45,
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
                        "value": "number",
                    },
                    "id": "879739879935337",
                },
                {"name": "pick", "inputs": {"obj": 39, "key": 24}},
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
                        "value": "number",
                    },
                    "id": "4266342207387543",
                },
                {"name": "pick", "inputs": {"obj": 39, "key": 27}},
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
                        "value": "string",
                    },
                    "id": "6691482997950818",
                },
                {"name": "pick", "inputs": {"obj": 39, "key": 30}},
                {
                    "nodeType": "output",
                    "fromOp": 51,
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
                        "value": "string",
                    },
                    "id": "3592459647598144",
                },
                {"name": "pick", "inputs": {"obj": 39, "key": 33}},
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
                        "value": "string",
                    },
                    "id": "5919773286034152",
                },
                {"name": "pick", "inputs": {"obj": 39, "key": 36}},
                {
                    "nodeType": "output",
                    "fromOp": 55,
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
                        "value": "number",
                    },
                    "id": "8517426965278686",
                },
                {"name": "pick", "inputs": {"obj": 56, "key": 18}},
                {
                    "nodeType": "output",
                    "fromOp": 57,
                    "type": {
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
                                    "propertyTypes": {"indexCheckpoint": "number"},
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
                                "_step": "number",
                                "_wandb": {
                                    "type": "typedDict",
                                    "propertyTypes": {"runtime": "number"},
                                },
                                "_runtime": "number",
                                "_timestamp": "number",
                                "small_table": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "extension": "string",
                                        "wb_object_type": "string",
                                        "path": "string",
                                    },
                                },
                            },
                        },
                    },
                    "id": "591291267901212",
                },
                {"name": "index", "inputs": {"arr": 4, "index": 58}},
                {"nodeType": "const", "type": "number", "val": 2},
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
                        "value": "number",
                    },
                    "id": "4290586483504333",
                },
                {"name": "pick", "inputs": {"obj": 56, "key": 21}},
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
                        "value": "number",
                    },
                    "id": "6395903666016537",
                },
                {"name": "pick", "inputs": {"obj": 56, "key": 24}},
                {
                    "nodeType": "output",
                    "fromOp": 64,
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
                        "value": "number",
                    },
                    "id": "8653165214869924",
                },
                {"name": "pick", "inputs": {"obj": 56, "key": 27}},
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
                        "value": "string",
                    },
                    "id": "6906098011060093",
                },
                {"name": "pick", "inputs": {"obj": 56, "key": 30}},
                {
                    "nodeType": "output",
                    "fromOp": 68,
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
                        "value": "string",
                    },
                    "id": "1910982834306033",
                },
                {"name": "pick", "inputs": {"obj": 56, "key": 33}},
                {
                    "nodeType": "output",
                    "fromOp": 70,
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
                        "value": "string",
                    },
                    "id": "7190659764616172",
                },
                {"name": "pick", "inputs": {"obj": 56, "key": 36}},
            ],
            "rootNodes": [
                0,
                19,
                22,
                25,
                28,
                31,
                34,
                37,
                42,
                44,
                46,
                48,
                50,
                52,
                54,
                59,
                61,
                63,
                65,
                67,
                69,
            ],
        }
    }
]
