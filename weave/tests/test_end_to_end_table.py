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
                    "id": "5367932688815243",
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
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": {"type": "list", "objectType": "run", "maxLength": 50},
                    },
                    "id": "5981012718708336",
                },
                {"name": "limit", "inputs": {"arr": 4, "limit": 10}},
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
                        "value": {"type": "list", "objectType": "run"},
                    },
                    "id": "8994115873573894",
                },
                {"name": "project-runs", "inputs": {"project": 6}},
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
                {"nodeType": "const", "type": "number", "val": 50},
            ],
            "rootNodes": [0],
        }
    }
]
