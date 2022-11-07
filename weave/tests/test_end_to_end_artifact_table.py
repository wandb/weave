from weave.server import _handle_request


def test_playback():
    for payload in [execute_payloads[-1]]:
        res = _handle_request(payload, True)
        assert "error" not in res


execute_payloads = [
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
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "none",
                    },
                    "id": "6042435059414349",
                },
                {
                    "name": "artifactVersion-file",
                    "inputs": {"artifactVersion": 2, "path": 14},
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
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifactVersion",
                    },
                    "id": "1515679257494597",
                },
                {
                    "name": "artifactMembership-artifactVersion",
                    "inputs": {"artifactMembership": 4},
                },
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
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifactMembership",
                    },
                    "id": "8702676768367582",
                },
                {
                    "name": "artifact-membershipForAlias",
                    "inputs": {"artifact": 6, "aliasName": 13},
                },
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
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifact",
                    },
                    "id": "2381175888039771",
                },
                {
                    "name": "project-artifact",
                    "inputs": {"project": 8, "artifactName": 12},
                },
                {
                    "nodeType": "output",
                    "fromOp": 9,
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
                    "inputs": {"entityName": 10, "projectName": 11},
                },
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "dev_public_tables"},
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "run-2mj2qxxg-small_table",
                },
                {"nodeType": "const", "type": "string", "val": "v0"},
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "small_table.table.json",
                },
            ],
            "rootNodes": [0],
        }
    }
]
