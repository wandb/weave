from weave.server import handle_request


def test_playback():
    from ..ecosystem import huggingface

    for payload in [execute_payloads[-1]]:
        res = handle_request(payload, True)
        assert "error" not in res


execute_payloads = [
    {
        "graphs": {
            "nodes": [
                {
                    "nodeType": "output",
                    "fromOp": 1,
                    "type": "any",
                    "id": "1941193047416787",
                },
                {"name": "op-model_render", "inputs": {"model_node": 2}},
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {},
                        "outputType": {
                            "type": "HFModelTextGeneration",
                            "_property_types": {
                                "_id": "string",
                                "_sha": "string",
                                "_pipeline_tag": "string",
                                "_tags": {"type": "list", "objectType": "string"},
                                "_downloads": "int",
                                "_likes": "int",
                                "_library_name": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                            },
                            "_base_type": {
                                "type": "HFModel",
                                "_property_types": {
                                    "_id": "string",
                                    "_sha": "string",
                                    "_pipeline_tag": "string",
                                    "_tags": {"type": "list", "objectType": "string"},
                                    "_downloads": "int",
                                    "_likes": "int",
                                    "_library_name": {
                                        "type": "union",
                                        "members": ["none", "string"],
                                    },
                                },
                            },
                        },
                    },
                    "val": {
                        "nodeType": "var",
                        "type": {
                            "type": "HFModelTextGeneration",
                            "_property_types": {
                                "_id": "string",
                                "_sha": "string",
                                "_pipeline_tag": "string",
                                "_tags": {"type": "list", "objectType": "string"},
                                "_downloads": "int",
                                "_likes": "int",
                                "_library_name": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                            },
                            "_base_type": {
                                "type": "HFModel",
                                "_property_types": {
                                    "_id": "string",
                                    "_sha": "string",
                                    "_pipeline_tag": "string",
                                    "_tags": {"type": "list", "objectType": "string"},
                                    "_downloads": "int",
                                    "_likes": "int",
                                    "_library_name": {
                                        "type": "union",
                                        "members": ["none", "string"],
                                    },
                                },
                            },
                        },
                        "varName": "model_node",
                    },
                },
                {
                    "nodeType": "var",
                    "type": {
                        "type": "HFModelTextGeneration",
                        "_property_types": {
                            "_id": "string",
                            "_sha": "string",
                            "_pipeline_tag": "string",
                            "_tags": {"type": "list", "objectType": "string"},
                            "_downloads": "int",
                            "_likes": "int",
                            "_library_name": {
                                "type": "union",
                                "members": ["none", "string"],
                            },
                        },
                        "_base_type": {
                            "type": "HFModel",
                            "_property_types": {
                                "_id": "string",
                                "_sha": "string",
                                "_pipeline_tag": "string",
                                "_tags": {"type": "list", "objectType": "string"},
                                "_downloads": "int",
                                "_likes": "int",
                                "_library_name": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                            },
                        },
                    },
                    "varName": "model_node",
                },
            ],
            "targetNodes": [0],
        }
    }
]
