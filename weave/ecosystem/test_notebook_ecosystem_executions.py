from weave.server import handle_request


def test_playback():
    from weave import ecosystem

    for payload in [execute_payloads[-1]]:
        res = handle_request(payload, True)
        res.results.unwrap()


execute_payloads = [
    {
        "graphs": {
            "nodes": [
                {"nodeType": "const", "type": "string", "val": "inherit"},
                {"nodeType": "const", "type": "string", "val": ""},
                {
                    "nodeType": "output",
                    "fromOp": 3,
                    "type": "number",
                    "id": "6965691728254189",
                },
                {"name": "tag-indexCheckpoint", "inputs": {"obj": 4}},
                {
                    "nodeType": "output",
                    "fromOp": 5,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"indexCheckpoint": "number"},
                        },
                        "value": {"type": "OpDef"},
                    },
                    "id": "5817702282560567",
                },
                {"name": "index", "inputs": {"arr": 6, "index": 12}},
                {
                    "nodeType": "output",
                    "fromOp": 7,
                    "type": {
                        "type": "list",
                        "objectType": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {"indexCheckpoint": "number"},
                            },
                            "value": {"type": "OpDef"},
                        },
                    },
                    "id": "2857565887621620",
                },
                {"name": "list-createIndexCheckpointTag", "inputs": {"arr": 8}},
                {
                    "nodeType": "output",
                    "fromOp": 9,
                    "type": {"type": "list", "objectType": {"type": "OpDef"}},
                    "id": "3688357283448756",
                },
                {"name": "Ecosystem-ops", "inputs": {"self": 10}},
                {
                    "nodeType": "output",
                    "fromOp": 11,
                    "type": {
                        "type": "Ecosystem",
                        "_orgs": {"type": "list", "objectType": "any"},
                        "_packages": {"type": "list", "objectType": {"type": "OpDef"}},
                        "_datasets": {"type": "list", "objectType": {"type": "OpDef"}},
                        "_models": {"type": "list", "objectType": "any"},
                        "_ops": {"type": "list", "objectType": {"type": "OpDef"}},
                        "_property_types": {
                            "_orgs": {"type": "list", "objectType": "any"},
                            "_packages": {
                                "type": "list",
                                "objectType": {"type": "OpDef"},
                            },
                            "_datasets": {
                                "type": "list",
                                "objectType": {"type": "OpDef"},
                            },
                            "_models": {"type": "list", "objectType": "any"},
                            "_ops": {"type": "list", "objectType": {"type": "OpDef"}},
                        },
                    },
                    "id": "8371329692561700",
                },
                {"name": "op-ecosystem", "inputs": {}},
                {"nodeType": "const", "type": "number", "val": 0},
                {
                    "nodeType": "output",
                    "fromOp": 14,
                    "type": "number",
                    "id": "5907007908746573",
                },
                {"name": "tag-indexCheckpoint", "inputs": {"obj": 15}},
                {
                    "nodeType": "output",
                    "fromOp": 16,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"indexCheckpoint": "number"},
                        },
                        "value": {"type": "OpDef"},
                    },
                    "id": "6457218123539456",
                },
                {"name": "index", "inputs": {"arr": 6, "index": 17}},
                {"nodeType": "const", "type": "number", "val": 1},
                {
                    "nodeType": "output",
                    "fromOp": 19,
                    "type": "number",
                    "id": "6997650288408352",
                },
                {"name": "tag-indexCheckpoint", "inputs": {"obj": 20}},
                {
                    "nodeType": "output",
                    "fromOp": 21,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"indexCheckpoint": "number"},
                        },
                        "value": {"type": "OpDef"},
                    },
                    "id": "3586667514912185",
                },
                {"name": "index", "inputs": {"arr": 6, "index": 22}},
                {"nodeType": "const", "type": "number", "val": 2},
                {
                    "nodeType": "output",
                    "fromOp": 24,
                    "type": "number",
                    "id": "7805106646043236",
                },
                {"name": "tag-indexCheckpoint", "inputs": {"obj": 25}},
                {
                    "nodeType": "output",
                    "fromOp": 26,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"indexCheckpoint": "number"},
                        },
                        "value": {"type": "OpDef"},
                    },
                    "id": "2587861762122901",
                },
                {"name": "index", "inputs": {"arr": 6, "index": 27}},
                {"nodeType": "const", "type": "number", "val": 3},
                {
                    "nodeType": "output",
                    "fromOp": 29,
                    "type": "number",
                    "id": "5057421628670159",
                },
                {"name": "count", "inputs": {"arr": 6}},
            ],
            "targetNodes": [0, 1, 2, 13, 18, 23, 28],
        }
    }
]
