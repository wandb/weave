from weave.server import _handle_request


def test_playback():
    for payload in execute_payloads:
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
                    "id": "6553957167377112",
                },
                {
                    "name": "project-artifact",
                    "inputs": {"project": 2, "artifactName": 6},
                },
                {
                    "nodeType": "output",
                    "fromOp": 3,
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
                {"name": "root-project", "inputs": {"entityName": 4, "projectName": 5}},
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "dev_public_tables"},
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "run-2ase1uju-small_table_9",
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
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "collectionName": {
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
                                "value": "string",
                            },
                            "collectionId": {
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
                                "value": "string",
                            },
                            "collectionIsPortfolio": {
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
                                "value": "boolean",
                            },
                            "collectionMemberships": {
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
                                "value": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "versionIndex": "number",
                                            "versionId": "artifactVersion",
                                            "aliases": {
                                                "type": "list",
                                                "objectType": "string",
                                            },
                                        },
                                    },
                                },
                            },
                            "versionCount": {
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
                                "value": "number",
                            },
                            "lastMembershipVersionIndex": {
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
                                "value": "number",
                            },
                            "entityName": {
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
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "artifactName": "string",
                                                },
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"entity": "entity"},
                                    },
                                },
                                "value": "string",
                            },
                            "projectName": {
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
                                                "artifactName": "string",
                                            },
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                },
                                "value": "string",
                            },
                            "artifactTypeName": {
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
                                "value": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                            },
                        },
                    },
                    "id": "6348532480684643",
                },
                {
                    "name": "dict",
                    "inputs": {
                        "collectionName": 2,
                        "collectionId": 11,
                        "collectionIsPortfolio": 13,
                        "collectionMemberships": 15,
                        "versionCount": 31,
                        "lastMembershipVersionIndex": 35,
                        "entityName": 39,
                        "projectName": 45,
                        "artifactTypeName": 49,
                    },
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
                        "value": "string",
                    },
                    "id": "4996065853565111",
                },
                {"name": "artifact-name", "inputs": {"artifact": 4}},
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
                        "value": "artifact",
                    },
                    "id": "6553957167377112",
                },
                {
                    "name": "project-artifact",
                    "inputs": {"project": 6, "artifactName": 10},
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
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "run-2ase1uju-small_table_9",
                },
                {
                    "nodeType": "output",
                    "fromOp": 12,
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
                        "value": "string",
                    },
                    "id": "8752272471586914",
                },
                {"name": "artifact-id", "inputs": {"artifact": 4}},
                {
                    "nodeType": "output",
                    "fromOp": 14,
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
                        "value": "boolean",
                    },
                    "id": "8398818135485002",
                },
                {"name": "artifact-isPortfolio", "inputs": {"artifact": 4}},
                {
                    "nodeType": "output",
                    "fromOp": 16,
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
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "versionIndex": "number",
                                    "versionId": "artifactVersion",
                                    "aliases": {"type": "list", "objectType": "string"},
                                },
                            },
                        },
                    },
                    "id": "3503944657262502",
                },
                {"name": "map", "inputs": {"arr": 17, "mapFn": 19}},
                {
                    "nodeType": "output",
                    "fromOp": 18,
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
                        "value": {"type": "list", "objectType": "artifactMembership"},
                    },
                    "id": "98477360533452",
                },
                {"name": "artifact-memberships", "inputs": {"artifact": 4}},
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifactMembership"},
                        "outputType": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "versionIndex": "number",
                                "versionId": "artifactVersion",
                                "aliases": {"type": "list", "objectType": "string"},
                            },
                        },
                    },
                    "val": {"nodeType": "output", "fromOp": 21},
                },
                {
                    "nodeType": "output",
                    "fromOp": 21,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "versionIndex": "number",
                            "versionId": "artifactVersion",
                            "aliases": {"type": "list", "objectType": "string"},
                        },
                    },
                    "id": "5970922106718874",
                },
                {
                    "name": "dict",
                    "inputs": {"versionIndex": 22, "versionId": 25, "aliases": 27},
                },
                {
                    "nodeType": "output",
                    "fromOp": 23,
                    "type": "number",
                    "id": "4925790233432165",
                },
                {
                    "name": "artifactMembership-versionIndex",
                    "inputs": {"artifactMembership": 24},
                },
                {"nodeType": "var", "type": "artifactMembership", "varName": "row"},
                {
                    "nodeType": "output",
                    "fromOp": 26,
                    "type": "artifactVersion",
                    "id": "2179539463484386",
                },
                {
                    "name": "artifactMembership-artifactVersion",
                    "inputs": {"artifactMembership": 24},
                },
                {
                    "nodeType": "output",
                    "fromOp": 28,
                    "type": {"type": "list", "objectType": "string"},
                    "id": "7980587611842290",
                },
                {"name": "artifactAlias-alias", "inputs": {"artifactAlias": 29}},
                {
                    "nodeType": "output",
                    "fromOp": 30,
                    "type": {"type": "list", "objectType": "artifactAlias"},
                    "id": "7032865535691260",
                },
                {
                    "name": "artifactMembership-aliases",
                    "inputs": {"artifactMembership": 24},
                },
                {
                    "nodeType": "output",
                    "fromOp": 32,
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
                        "value": "number",
                    },
                    "id": "2988714989197160",
                },
                {"name": "count", "inputs": {"arr": 33}},
                {
                    "nodeType": "output",
                    "fromOp": 34,
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
                        "value": {"type": "list", "objectType": "artifactVersion"},
                    },
                    "id": "8601379792703931",
                },
                {"name": "artifact-versions", "inputs": {"artifact": 4}},
                {
                    "nodeType": "output",
                    "fromOp": 36,
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
                        "value": "number",
                    },
                    "id": "414169658372316",
                },
                {
                    "name": "artifactMembership-versionIndex",
                    "inputs": {"artifactMembership": 37},
                },
                {
                    "nodeType": "output",
                    "fromOp": 38,
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
                    "id": "8517216737128038",
                },
                {"name": "artifact-lastMembership", "inputs": {"artifact": 4}},
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
                                        "propertyTypes": {
                                            "project": "project",
                                            "artifactName": "string",
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "991475556502462",
                },
                {"name": "entity-name", "inputs": {"entity": 41}},
                {
                    "nodeType": "output",
                    "fromOp": 42,
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
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "entity",
                    },
                    "id": "22964138590358",
                },
                {"name": "project-entity", "inputs": {"project": 43}},
                {
                    "nodeType": "output",
                    "fromOp": 44,
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
                        "value": "project",
                    },
                    "id": "6075194553732621",
                },
                {"name": "artifact-project", "inputs": {"artifact": 4}},
                {
                    "nodeType": "output",
                    "fromOp": 46,
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
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "6543117012015410",
                },
                {"name": "project-name", "inputs": {"project": 47}},
                {
                    "nodeType": "output",
                    "fromOp": 48,
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
                        "value": "project",
                    },
                    "id": "6075194553732621",
                },
                {"name": "artifact-project", "inputs": {"artifact": 4}},
                {
                    "nodeType": "output",
                    "fromOp": 50,
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
                        "value": {"type": "union", "members": ["none", "string"]},
                    },
                    "id": "3361247100281371",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 51}},
                {
                    "nodeType": "output",
                    "fromOp": 52,
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
                        "value": {"type": "union", "members": ["none", "artifactType"]},
                    },
                    "id": "4945095640328687",
                },
                {"name": "artifact-type", "inputs": {"artifact": 4}},
                {
                    "nodeType": "output",
                    "fromOp": 54,
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
                    "id": "4183561500480054",
                },
                {
                    "name": "artifact-membershipForAlias",
                    "inputs": {"artifact": 4, "aliasName": 55},
                },
                {"nodeType": "const", "type": "string", "val": "v0"},
                {
                    "nodeType": "output",
                    "fromOp": 57,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "index": {
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
                                "value": "number",
                            },
                            "id": {
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
                                "value": "string",
                            },
                        },
                    },
                    "id": "7809256894652066",
                },
                {"name": "dict", "inputs": {"index": 58, "id": 60}},
                {
                    "nodeType": "output",
                    "fromOp": 59,
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
                        "value": "number",
                    },
                    "id": "4124428281791671",
                },
                {
                    "name": "artifactMembership-versionIndex",
                    "inputs": {"artifactMembership": 53},
                },
                {
                    "nodeType": "output",
                    "fromOp": 61,
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
                        "value": "string",
                    },
                    "id": "3549685395095410",
                },
                {"name": "artifactVersion-id", "inputs": {"artifactVersion": 62}},
                {
                    "nodeType": "output",
                    "fromOp": 63,
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
                    "id": "4143584412185738",
                },
                {
                    "name": "artifactMembership-artifactVersion",
                    "inputs": {"artifactMembership": 53},
                },
            ],
            "rootNodes": [0, 53, 56],
        }
    },
    {
        "graphs": {
            "nodes": [
                {
                    "nodeType": "output",
                    "fromOp": 1,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "artifactVersionId": {
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
                                "value": "string",
                            },
                            "artifactId": {
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
                                "value": "string",
                            },
                            "artifactAliases": {
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
                                "value": {"type": "list", "objectType": "string"},
                            },
                            "artifactTypeName": {
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
                                "value": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                            },
                            "artifactMembershipsMaterialized": {
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
                                "value": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "versionIndex": "number",
                                            "aliases": {
                                                "type": "list",
                                                "objectType": "string",
                                            },
                                        },
                                    },
                                },
                            },
                            "entityName": {
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
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "artifactName": "string",
                                                },
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"entity": "entity"},
                                    },
                                },
                                "value": "string",
                            },
                            "projectName": {
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
                                                "artifactName": "string",
                                            },
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                },
                                "value": "string",
                            },
                            "artifactName": {
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
                                "value": "string",
                            },
                            "versionIndex": {
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
                                "value": "number",
                            },
                            "versionDescription": {
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
                                "value": "string",
                            },
                            "digest": {
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
                                "value": "string",
                            },
                            "createdAt": {
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
                                "value": {"type": "timestamp", "unit": "ms"},
                            },
                            "numConsumers": {
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
                                "value": "number",
                            },
                            "numFiles": {
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
                                "value": "number",
                            },
                            "artifactSize": {
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
                                "value": "number",
                            },
                            "artifactIsPortfolio": {
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
                                "value": "boolean",
                            },
                            "portfolioMemberships": {
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
                                "value": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "name": "string",
                                            "typeName": {
                                                "type": "union",
                                                "members": ["none", "string"],
                                            },
                                            "project": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    },
                                                },
                                                "value": "string",
                                            },
                                            "entity": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "project": "project"
                                                        },
                                                    },
                                                    "value": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "entity": "entity"
                                                        },
                                                    },
                                                },
                                                "value": "string",
                                            },
                                        },
                                    },
                                },
                            },
                            "peerArtifacts": {
                                "type": "union",
                                "members": [
                                    {
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
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"run": "run"},
                                            },
                                        },
                                        "value": {
                                            "type": "list",
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "versionName": "string",
                                                    "type": "string",
                                                    "entityName": {
                                                        "type": "tagged",
                                                        "tag": {
                                                            "type": "tagged",
                                                            "tag": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "project": "project"
                                                                },
                                                            },
                                                            "value": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "entity": "entity"
                                                                },
                                                            },
                                                        },
                                                        "value": "string",
                                                    },
                                                    "projectName": {
                                                        "type": "tagged",
                                                        "tag": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "project": "project"
                                                            },
                                                        },
                                                        "value": "string",
                                                    },
                                                },
                                            },
                                        },
                                    },
                                ],
                            },
                            "canLink": {
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
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "artifactName": "string",
                                                },
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"entity": "entity"},
                                    },
                                },
                                "value": "boolean",
                            },
                        },
                    },
                    "id": "2019201670528033",
                },
                {
                    "name": "dict",
                    "inputs": {
                        "artifactVersionId": 2,
                        "artifactId": 16,
                        "artifactAliases": 20,
                        "artifactTypeName": 24,
                        "artifactMembershipsMaterialized": 28,
                        "entityName": 42,
                        "projectName": 48,
                        "artifactName": 50,
                        "versionIndex": 52,
                        "versionDescription": 54,
                        "digest": 58,
                        "createdAt": 60,
                        "numConsumers": 62,
                        "numFiles": 66,
                        "artifactSize": 70,
                        "artifactIsPortfolio": 72,
                        "portfolioMemberships": 74,
                        "peerArtifacts": 104,
                        "canLink": 134,
                    },
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
                        "value": "string",
                    },
                    "id": "3549685395095410",
                },
                {"name": "artifactVersion-id", "inputs": {"artifactVersion": 4}},
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
                        "value": "artifactVersion",
                    },
                    "id": "4143584412185738",
                },
                {
                    "name": "artifactMembership-artifactVersion",
                    "inputs": {"artifactMembership": 6},
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
                        "value": "artifactMembership",
                    },
                    "id": "4183561500480054",
                },
                {
                    "name": "artifact-membershipForAlias",
                    "inputs": {"artifact": 8, "aliasName": 15},
                },
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
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifact",
                    },
                    "id": "6553957167377112",
                },
                {
                    "name": "project-artifact",
                    "inputs": {"project": 10, "artifactName": 14},
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
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "run-2ase1uju-small_table_9",
                },
                {"nodeType": "const", "type": "string", "val": "v0"},
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
                        "value": "string",
                    },
                    "id": "176649145590468",
                },
                {"name": "artifact-id", "inputs": {"artifact": 18}},
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
                    "id": "5475877935812382",
                },
                {
                    "name": "artifactMembership-collection",
                    "inputs": {"artifactMembership": 6},
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
                        "value": {"type": "list", "objectType": "string"},
                    },
                    "id": "3503752260754309",
                },
                {"name": "artifactAlias-alias", "inputs": {"artifactAlias": 22}},
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
                        "value": {"type": "list", "objectType": "artifactAlias"},
                    },
                    "id": "2622621321783749",
                },
                {"name": "artifact-aliases", "inputs": {"artifact": 18}},
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
                        "value": {"type": "union", "members": ["none", "string"]},
                    },
                    "id": "8614143706905554",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 26}},
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
                        "value": {"type": "union", "members": ["none", "artifactType"]},
                    },
                    "id": "6632259454337532",
                },
                {"name": "artifact-type", "inputs": {"artifact": 18}},
                {
                    "nodeType": "output",
                    "fromOp": 29,
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
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "versionIndex": "number",
                                    "aliases": {"type": "list", "objectType": "string"},
                                },
                            },
                        },
                    },
                    "id": "2767032505114524",
                },
                {"name": "map", "inputs": {"arr": 30, "mapFn": 32}},
                {
                    "nodeType": "output",
                    "fromOp": 31,
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
                        "value": {"type": "list", "objectType": "artifactMembership"},
                    },
                    "id": "472977661868851",
                },
                {"name": "artifact-memberships", "inputs": {"artifact": 18}},
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifactMembership"},
                        "outputType": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "versionIndex": "number",
                                "aliases": {"type": "list", "objectType": "string"},
                            },
                        },
                    },
                    "val": {"nodeType": "output", "fromOp": 34},
                },
                {
                    "nodeType": "output",
                    "fromOp": 34,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "versionIndex": "number",
                            "aliases": {"type": "list", "objectType": "string"},
                        },
                    },
                    "id": "3094001597801100",
                },
                {"name": "dict", "inputs": {"versionIndex": 35, "aliases": 38}},
                {
                    "nodeType": "output",
                    "fromOp": 36,
                    "type": "number",
                    "id": "4925790233432165",
                },
                {
                    "name": "artifactMembership-versionIndex",
                    "inputs": {"artifactMembership": 37},
                },
                {"nodeType": "var", "type": "artifactMembership", "varName": "row"},
                {
                    "nodeType": "output",
                    "fromOp": 39,
                    "type": {"type": "list", "objectType": "string"},
                    "id": "7980587611842290",
                },
                {"name": "artifactAlias-alias", "inputs": {"artifactAlias": 40}},
                {
                    "nodeType": "output",
                    "fromOp": 41,
                    "type": {"type": "list", "objectType": "artifactAlias"},
                    "id": "7032865535691260",
                },
                {
                    "name": "artifactMembership-aliases",
                    "inputs": {"artifactMembership": 37},
                },
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
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "648687364178050",
                },
                {"name": "entity-name", "inputs": {"entity": 44}},
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
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "entity",
                    },
                    "id": "1241158750535986",
                },
                {"name": "project-entity", "inputs": {"project": 46}},
                {
                    "nodeType": "output",
                    "fromOp": 47,
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
                        "value": "project",
                    },
                    "id": "7822866300892919",
                },
                {"name": "artifact-project", "inputs": {"artifact": 18}},
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
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "484262008073823",
                },
                {"name": "project-name", "inputs": {"project": 46}},
                {
                    "nodeType": "output",
                    "fromOp": 51,
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
                        "value": "string",
                    },
                    "id": "8193309372949031",
                },
                {"name": "artifact-name", "inputs": {"artifact": 18}},
                {
                    "nodeType": "output",
                    "fromOp": 53,
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
                        "value": "number",
                    },
                    "id": "4124428281791671",
                },
                {
                    "name": "artifactMembership-versionIndex",
                    "inputs": {"artifactMembership": 6},
                },
                {
                    "nodeType": "output",
                    "fromOp": 55,
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
                        "value": "string",
                    },
                    "id": "1692322000503552",
                },
                {
                    "name": "artifactVersion-description",
                    "inputs": {"artifactVersion": 56},
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
                    "id": "4143584412185738",
                },
                {
                    "name": "artifactMembership-artifactVersion",
                    "inputs": {"artifactMembership": 6},
                },
                {
                    "nodeType": "output",
                    "fromOp": 59,
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
                        "value": "string",
                    },
                    "id": "7541644436309802",
                },
                {"name": "artifactVersion-digest", "inputs": {"artifactVersion": 56}},
                {
                    "nodeType": "output",
                    "fromOp": 61,
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
                        "value": {"type": "timestamp", "unit": "ms"},
                    },
                    "id": "2717326015999597",
                },
                {
                    "name": "artifactVersion-createdAt",
                    "inputs": {"artifactVersion": 56},
                },
                {
                    "nodeType": "output",
                    "fromOp": 63,
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
                        "value": "number",
                    },
                    "id": "6296531790248382",
                },
                {"name": "count", "inputs": {"arr": 64}},
                {
                    "nodeType": "output",
                    "fromOp": 65,
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
                        "value": {"type": "list", "objectType": "run"},
                    },
                    "id": "3515032507094279",
                },
                {"name": "artifactVersion-usedBy", "inputs": {"artifactVersion": 56}},
                {
                    "nodeType": "output",
                    "fromOp": 67,
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
                        "value": "number",
                    },
                    "id": "5874113725498422",
                },
                {"name": "count", "inputs": {"arr": 68}},
                {
                    "nodeType": "output",
                    "fromOp": 69,
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
                        "value": {"type": "list", "objectType": {"type": "file"}},
                    },
                    "id": "8552743299492105",
                },
                {"name": "artifactVersion-files", "inputs": {"artifactVersion": 56}},
                {
                    "nodeType": "output",
                    "fromOp": 71,
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
                        "value": "number",
                    },
                    "id": "5841098403620185",
                },
                {"name": "artifactVersion-size", "inputs": {"artifactVersion": 56}},
                {
                    "nodeType": "output",
                    "fromOp": 73,
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
                        "value": "boolean",
                    },
                    "id": "7854043332320847",
                },
                {"name": "artifact-isPortfolio", "inputs": {"artifact": 18}},
                {
                    "nodeType": "output",
                    "fromOp": 75,
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
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "name": "string",
                                    "typeName": {
                                        "type": "union",
                                        "members": ["none", "string"],
                                    },
                                    "project": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                        "value": "string",
                                    },
                                    "entity": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {"project": "project"},
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"entity": "entity"},
                                            },
                                        },
                                        "value": "string",
                                    },
                                },
                            },
                        },
                    },
                    "id": "5831346114323342",
                },
                {"name": "map", "inputs": {"arr": 76, "mapFn": 84}},
                {
                    "nodeType": "output",
                    "fromOp": 77,
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
                        "value": {"type": "list", "objectType": "artifact"},
                    },
                    "id": "2031374762905722",
                },
                {"name": "filter", "inputs": {"arr": 78, "filterFn": 80}},
                {
                    "nodeType": "output",
                    "fromOp": 79,
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
                        "value": {"type": "list", "objectType": "artifact"},
                    },
                    "id": "7298654055426105",
                },
                {
                    "name": "artifactVersion-artifactCollections",
                    "inputs": {"artifactVersion": 56},
                },
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifact"},
                        "outputType": "boolean",
                    },
                    "val": {"nodeType": "output", "fromOp": 82},
                },
                {
                    "nodeType": "output",
                    "fromOp": 82,
                    "type": "boolean",
                    "id": "8311114900625188",
                },
                {"name": "artifact-isPortfolio", "inputs": {"artifact": 83}},
                {"nodeType": "var", "type": "artifact", "varName": "row"},
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifact"},
                        "outputType": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "name": "string",
                                "typeName": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                                "project": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                    "value": "string",
                                },
                                "entity": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"entity": "entity"},
                                        },
                                    },
                                    "value": "string",
                                },
                            },
                        },
                    },
                    "val": {"nodeType": "output", "fromOp": 86},
                },
                {
                    "nodeType": "output",
                    "fromOp": 86,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "name": "string",
                            "typeName": {
                                "type": "union",
                                "members": ["none", "string"],
                            },
                            "project": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                                "value": "string",
                            },
                            "entity": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"entity": "entity"},
                                    },
                                },
                                "value": "string",
                            },
                        },
                    },
                    "id": "8084333411776374",
                },
                {
                    "name": "dict",
                    "inputs": {"name": 87, "typeName": 90, "project": 94, "entity": 98},
                },
                {
                    "nodeType": "output",
                    "fromOp": 88,
                    "type": "string",
                    "id": "2836867465098471",
                },
                {"name": "artifact-name", "inputs": {"artifact": 89}},
                {"nodeType": "var", "type": "artifact", "varName": "row"},
                {
                    "nodeType": "output",
                    "fromOp": 91,
                    "type": {"type": "union", "members": ["none", "string"]},
                    "id": "3757465892811307",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 92}},
                {
                    "nodeType": "output",
                    "fromOp": 93,
                    "type": {"type": "union", "members": ["none", "artifactType"]},
                    "id": "4045941319649867",
                },
                {"name": "artifact-type", "inputs": {"artifact": 89}},
                {
                    "nodeType": "output",
                    "fromOp": 95,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"project": "project"},
                        },
                        "value": "string",
                    },
                    "id": "2305183914378038",
                },
                {"name": "project-name", "inputs": {"project": 96}},
                {
                    "nodeType": "output",
                    "fromOp": 97,
                    "type": "project",
                    "id": "2437352500364524",
                },
                {"name": "artifact-project", "inputs": {"artifact": 89}},
                {
                    "nodeType": "output",
                    "fromOp": 99,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "8774612696788142",
                },
                {"name": "entity-name", "inputs": {"entity": 100}},
                {
                    "nodeType": "output",
                    "fromOp": 101,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"project": "project"},
                        },
                        "value": "entity",
                    },
                    "id": "8748009072814723",
                },
                {"name": "project-entity", "inputs": {"project": 102}},
                {
                    "nodeType": "output",
                    "fromOp": 103,
                    "type": "project",
                    "id": "2437352500364524",
                },
                {"name": "artifact-project", "inputs": {"artifact": 89}},
                {
                    "nodeType": "output",
                    "fromOp": 105,
                    "type": {
                        "type": "union",
                        "members": [
                            {
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
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                },
                                "value": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "versionName": "string",
                                            "type": "string",
                                            "entityName": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "project": "project"
                                                        },
                                                    },
                                                    "value": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "entity": "entity"
                                                        },
                                                    },
                                                },
                                                "value": "string",
                                            },
                                            "projectName": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "project": "project"
                                                    },
                                                },
                                                "value": "string",
                                            },
                                        },
                                    },
                                },
                            },
                        ],
                    },
                    "id": "7538904847463431",
                },
                {"name": "map", "inputs": {"arr": 106, "mapFn": 110}},
                {
                    "nodeType": "output",
                    "fromOp": 107,
                    "type": {
                        "type": "union",
                        "members": [
                            {
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
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                },
                                "value": {
                                    "type": "list",
                                    "objectType": "artifactVersion",
                                },
                            },
                        ],
                    },
                    "id": "124465328196525",
                },
                {"name": "run-usedArtifactVersions", "inputs": {"run": 108}},
                {
                    "nodeType": "output",
                    "fromOp": 109,
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
                        "value": {"type": "union", "members": ["none", "run"]},
                    },
                    "id": "8170865822461107",
                },
                {
                    "name": "artifactVersion-createdBy",
                    "inputs": {"artifactVersion": 56},
                },
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifactVersion"},
                        "outputType": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "versionName": "string",
                                "type": "string",
                                "entityName": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"entity": "entity"},
                                        },
                                    },
                                    "value": "string",
                                },
                                "projectName": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                    "value": "string",
                                },
                            },
                        },
                    },
                    "val": {"nodeType": "output", "fromOp": 112},
                },
                {
                    "nodeType": "output",
                    "fromOp": 112,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "versionName": "string",
                            "type": "string",
                            "entityName": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"entity": "entity"},
                                    },
                                },
                                "value": "string",
                            },
                            "projectName": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                                "value": "string",
                            },
                        },
                    },
                    "id": "4235004977617998",
                },
                {
                    "name": "dict",
                    "inputs": {
                        "versionName": 113,
                        "type": 116,
                        "entityName": 120,
                        "projectName": 128,
                    },
                },
                {
                    "nodeType": "output",
                    "fromOp": 114,
                    "type": "string",
                    "id": "4450167607005980",
                },
                {"name": "artifactVersion-name", "inputs": {"artifactVersion": 115}},
                {"nodeType": "var", "type": "artifactVersion", "varName": "row"},
                {
                    "nodeType": "output",
                    "fromOp": 117,
                    "type": "string",
                    "id": "803419841034606",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 118}},
                {
                    "nodeType": "output",
                    "fromOp": 119,
                    "type": "artifactType",
                    "id": "7310983721734015",
                },
                {
                    "name": "artifactVersion-artifactType",
                    "inputs": {"artifactVersion": 115},
                },
                {
                    "nodeType": "output",
                    "fromOp": 121,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "1687420381025483",
                },
                {"name": "entity-name", "inputs": {"entity": 122}},
                {
                    "nodeType": "output",
                    "fromOp": 123,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"project": "project"},
                        },
                        "value": "entity",
                    },
                    "id": "7615739945566212",
                },
                {"name": "project-entity", "inputs": {"project": 124}},
                {
                    "nodeType": "output",
                    "fromOp": 125,
                    "type": "project",
                    "id": "8729910544631685",
                },
                {"name": "artifact-project", "inputs": {"artifact": 126}},
                {
                    "nodeType": "output",
                    "fromOp": 127,
                    "type": "artifact",
                    "id": "7162691277092701",
                },
                {
                    "name": "artifactVersion-artifactSequence",
                    "inputs": {"artifactVersion": 115},
                },
                {
                    "nodeType": "output",
                    "fromOp": 129,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"project": "project"},
                        },
                        "value": "string",
                    },
                    "id": "3475449232027384",
                },
                {"name": "project-name", "inputs": {"project": 130}},
                {
                    "nodeType": "output",
                    "fromOp": 131,
                    "type": "project",
                    "id": "8729910544631685",
                },
                {"name": "artifact-project", "inputs": {"artifact": 132}},
                {
                    "nodeType": "output",
                    "fromOp": 133,
                    "type": "artifact",
                    "id": "7162691277092701",
                },
                {
                    "name": "artifactVersion-artifactSequence",
                    "inputs": {"artifactVersion": 115},
                },
                {
                    "nodeType": "output",
                    "fromOp": 135,
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
                                        "propertyTypes": {
                                            "project": "project",
                                            "artifactName": "string",
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "boolean",
                    },
                    "id": "8868158163515159",
                },
                {"name": "number-greaterEqual", "inputs": {"lhs": 136, "rhs": 154}},
                {
                    "nodeType": "output",
                    "fromOp": 137,
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
                                        "propertyTypes": {
                                            "project": "project",
                                            "artifactName": "string",
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "number",
                    },
                    "id": "8574339178499141",
                },
                {"name": "count", "inputs": {"arr": 138}},
                {
                    "nodeType": "output",
                    "fromOp": 139,
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
                                        "propertyTypes": {
                                            "project": "project",
                                            "artifactName": "string",
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": {"type": "list", "objectType": "artifact"},
                    },
                    "id": "5320389980049179",
                },
                {"name": "filter", "inputs": {"arr": 140, "filterFn": 144}},
                {
                    "nodeType": "output",
                    "fromOp": 141,
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
                                        "propertyTypes": {
                                            "project": "project",
                                            "artifactName": "string",
                                        },
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": {"type": "list", "objectType": "artifact"},
                    },
                    "id": "2166004363018583",
                },
                {"name": "entity-portfolios", "inputs": {"entity": 142}},
                {
                    "nodeType": "output",
                    "fromOp": 143,
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
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "entity",
                    },
                    "id": "1241158750535986",
                },
                {"name": "project-entity", "inputs": {"project": 46}},
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifact"},
                        "outputType": {"type": "union", "members": ["none", "boolean"]},
                    },
                    "val": {"nodeType": "output", "fromOp": 146},
                },
                {
                    "nodeType": "output",
                    "fromOp": 146,
                    "type": {"type": "union", "members": ["none", "boolean"]},
                    "id": "7255905037059840",
                },
                {"name": "string-equal", "inputs": {"lhs": 147, "rhs": 152}},
                {
                    "nodeType": "output",
                    "fromOp": 148,
                    "type": {"type": "union", "members": ["none", "string"]},
                    "id": "3757465892811307",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 149}},
                {
                    "nodeType": "output",
                    "fromOp": 150,
                    "type": {"type": "union", "members": ["none", "artifactType"]},
                    "id": "4045941319649867",
                },
                {"name": "artifact-type", "inputs": {"artifact": 151}},
                {"nodeType": "var", "type": "artifact", "varName": "row"},
                {
                    "nodeType": "output",
                    "fromOp": 153,
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
                        "value": {"type": "union", "members": ["none", "string"]},
                    },
                    "id": "8614143706905554",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 26}},
                {"nodeType": "const", "type": "number", "val": 1},
                {
                    "nodeType": "output",
                    "fromOp": 156,
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
                        "value": "number",
                    },
                    "id": "7900553303104105",
                },
                {"name": "count", "inputs": {"arr": 157}},
                {
                    "nodeType": "output",
                    "fromOp": 158,
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
                        "value": {"type": "list", "objectType": "artifactMembership"},
                    },
                    "id": "2483291947099134",
                },
                {"name": "filter", "inputs": {"arr": 159, "filterFn": 161}},
                {
                    "nodeType": "output",
                    "fromOp": 160,
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
                        "value": {"type": "list", "objectType": "artifactMembership"},
                    },
                    "id": "5937444391107259",
                },
                {
                    "name": "artifactVersion-memberships",
                    "inputs": {"artifactVersion": 56},
                },
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifactMembership"},
                        "outputType": "boolean",
                    },
                    "val": {"nodeType": "output", "fromOp": 163},
                },
                {
                    "nodeType": "output",
                    "fromOp": 163,
                    "type": "boolean",
                    "id": "1981533946648906",
                },
                {"name": "artifact-isPortfolio", "inputs": {"artifact": 164}},
                {
                    "nodeType": "output",
                    "fromOp": 165,
                    "type": "artifact",
                    "id": "3646341583176945",
                },
                {
                    "name": "artifactMembership-collection",
                    "inputs": {"artifactMembership": 166},
                },
                {"nodeType": "var", "type": "artifactMembership", "varName": "row"},
                {
                    "nodeType": "output",
                    "fromOp": 168,
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
                        "value": "boolean",
                    },
                    "id": "7844623079203603",
                },
                {
                    "name": "artifactVersion-isWeaveObject",
                    "inputs": {"artifactVersion": 169},
                },
                {
                    "nodeType": "output",
                    "fromOp": 170,
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
                    "id": "4143584412185738",
                },
                {
                    "name": "artifactMembership-artifactVersion",
                    "inputs": {"artifactMembership": 6},
                },
            ],
            "rootNodes": [0, 155, 167],
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
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "link",
                    },
                    "id": "3390194197721611",
                },
                {"name": "entity-link", "inputs": {"entity": 2}},
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
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "entity",
                    },
                    "id": "1241158750535986",
                },
                {"name": "project-entity", "inputs": {"project": 4}},
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
                        "value": "project",
                    },
                    "id": "7822866300892919",
                },
                {"name": "artifact-project", "inputs": {"artifact": 6}},
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
                    "id": "5475877935812382",
                },
                {
                    "name": "artifactMembership-collection",
                    "inputs": {"artifactMembership": 8},
                },
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
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifactMembership",
                    },
                    "id": "4183561500480054",
                },
                {
                    "name": "artifact-membershipForAlias",
                    "inputs": {"artifact": 10, "aliasName": 17},
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
                    "id": "6553957167377112",
                },
                {
                    "name": "project-artifact",
                    "inputs": {"project": 12, "artifactName": 16},
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
                    "id": "1228024693382936",
                },
                {
                    "name": "root-project",
                    "inputs": {"entityName": 14, "projectName": 15},
                },
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {"nodeType": "const", "type": "string", "val": "dev_public_tables"},
                {
                    "nodeType": "const",
                    "type": "string",
                    "val": "run-2ase1uju-small_table_9",
                },
                {"nodeType": "const", "type": "string", "val": "v0"},
                {
                    "nodeType": "output",
                    "fromOp": 19,
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
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "link",
                    },
                    "id": "4329317706728338",
                },
                {"name": "project-link", "inputs": {"project": 20}},
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
                        "value": "project",
                    },
                    "id": "7822866300892919",
                },
                {"name": "artifact-project", "inputs": {"artifact": 6}},
                {
                    "nodeType": "output",
                    "fromOp": 23,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "artifactId": {
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
                                "value": "string",
                            },
                            "artifactName": {
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
                                "value": "string",
                            },
                            "artifactDescription": {
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
                                "value": "string",
                            },
                            "artifactCreatedAt": {
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
                                "value": "date",
                            },
                            "artifactAliases": {
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
                                "value": {"type": "list", "objectType": "string"},
                            },
                            "artifactTypeName": {
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
                                "value": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                            },
                            "artifactIsPortfolio": {
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
                                "value": "boolean",
                            },
                        },
                    },
                    "id": "7412599091484631",
                },
                {
                    "name": "dict",
                    "inputs": {
                        "artifactId": 24,
                        "artifactName": 26,
                        "artifactDescription": 28,
                        "artifactCreatedAt": 30,
                        "artifactAliases": 32,
                        "artifactTypeName": 36,
                        "artifactIsPortfolio": 40,
                    },
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
                        "value": "string",
                    },
                    "id": "176649145590468",
                },
                {"name": "artifact-id", "inputs": {"artifact": 6}},
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
                        "value": "string",
                    },
                    "id": "8193309372949031",
                },
                {"name": "artifact-name", "inputs": {"artifact": 6}},
                {
                    "nodeType": "output",
                    "fromOp": 29,
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
                        "value": "string",
                    },
                    "id": "4595024685155056",
                },
                {"name": "artifact-description", "inputs": {"artifact": 6}},
                {
                    "nodeType": "output",
                    "fromOp": 31,
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
                        "value": "date",
                    },
                    "id": "962297071763745",
                },
                {"name": "artifact-createdAt", "inputs": {"artifact": 6}},
                {
                    "nodeType": "output",
                    "fromOp": 33,
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
                        "value": {"type": "list", "objectType": "string"},
                    },
                    "id": "3503752260754309",
                },
                {"name": "artifactAlias-alias", "inputs": {"artifactAlias": 34}},
                {
                    "nodeType": "output",
                    "fromOp": 35,
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
                        "value": {"type": "list", "objectType": "artifactAlias"},
                    },
                    "id": "2622621321783749",
                },
                {"name": "artifact-aliases", "inputs": {"artifact": 6}},
                {
                    "nodeType": "output",
                    "fromOp": 37,
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
                        "value": {"type": "union", "members": ["none", "string"]},
                    },
                    "id": "8614143706905554",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 38}},
                {
                    "nodeType": "output",
                    "fromOp": 39,
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
                        "value": {"type": "union", "members": ["none", "artifactType"]},
                    },
                    "id": "6632259454337532",
                },
                {"name": "artifact-type", "inputs": {"artifact": 6}},
                {
                    "nodeType": "output",
                    "fromOp": 41,
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
                        "value": "boolean",
                    },
                    "id": "7854043332320847",
                },
                {"name": "artifact-isPortfolio", "inputs": {"artifact": 6}},
                {
                    "nodeType": "output",
                    "fromOp": 43,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "artifactName": {
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
                                "value": "string",
                            },
                            "projectName": {
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
                                                "artifactName": "string",
                                            },
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                },
                                "value": "string",
                            },
                            "entityName": {
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
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "artifactName": "string",
                                                },
                                            },
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"entity": "entity"},
                                    },
                                },
                                "value": "string",
                            },
                            "artifactAliases": {
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
                                "value": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "alias": "string",
                                            "artifactCollectionName": "string",
                                        },
                                    },
                                },
                            },
                            "artifactVersionId": {
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
                                "value": "string",
                            },
                            "currentAliases": {
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
                                "value": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "alias": "string",
                                            "artifactCollectionName": "string",
                                        },
                                    },
                                },
                            },
                            "allAliases": {
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
                                "value": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "alias": "string",
                                            "artifactCollectionName": "string",
                                        },
                                    },
                                },
                            },
                            "artifactMemberships": {
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
                                "value": {
                                    "type": "list",
                                    "objectType": "artifactMembership",
                                },
                            },
                            "isPortfolio": {
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
                                "value": "boolean",
                            },
                        },
                    },
                    "id": "7434788974184675",
                },
                {
                    "name": "dict",
                    "inputs": {
                        "artifactName": 44,
                        "projectName": 48,
                        "entityName": 52,
                        "artifactAliases": 58,
                        "artifactVersionId": 72,
                        "currentAliases": 76,
                        "allAliases": 80,
                        "artifactMemberships": 85,
                        "isPortfolio": 87,
                    },
                },
                {
                    "nodeType": "output",
                    "fromOp": 45,
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
                        "value": "string",
                    },
                    "id": "8193309372949031",
                },
                {"name": "artifact-name", "inputs": {"artifact": 46}},
                {
                    "nodeType": "output",
                    "fromOp": 47,
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
                    "id": "5475877935812382",
                },
                {
                    "name": "artifactMembership-collection",
                    "inputs": {"artifactMembership": 8},
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
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "484262008073823",
                },
                {"name": "project-name", "inputs": {"project": 50}},
                {
                    "nodeType": "output",
                    "fromOp": 51,
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
                        "value": "project",
                    },
                    "id": "7822866300892919",
                },
                {"name": "artifact-project", "inputs": {"artifact": 46}},
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
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "648687364178050",
                },
                {"name": "entity-name", "inputs": {"entity": 54}},
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
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                        },
                        "value": "entity",
                    },
                    "id": "1241158750535986",
                },
                {"name": "project-entity", "inputs": {"project": 56}},
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
                        "value": "project",
                    },
                    "id": "7822866300892919",
                },
                {"name": "artifact-project", "inputs": {"artifact": 46}},
                {
                    "nodeType": "output",
                    "fromOp": 59,
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
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "alias": "string",
                                    "artifactCollectionName": "string",
                                },
                            },
                        },
                    },
                    "id": "5320650081931056",
                },
                {"name": "map", "inputs": {"arr": 60, "mapFn": 62}},
                {
                    "nodeType": "output",
                    "fromOp": 61,
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
                        "value": {"type": "list", "objectType": "artifactAlias"},
                    },
                    "id": "2622621321783749",
                },
                {"name": "artifact-aliases", "inputs": {"artifact": 46}},
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifactAlias"},
                        "outputType": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "alias": "string",
                                "artifactCollectionName": "string",
                            },
                        },
                    },
                    "val": {"nodeType": "output", "fromOp": 64},
                },
                {
                    "nodeType": "output",
                    "fromOp": 64,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "alias": "string",
                            "artifactCollectionName": "string",
                        },
                    },
                    "id": "3291184882484821",
                },
                {"name": "dict", "inputs": {"alias": 65, "artifactCollectionName": 68}},
                {
                    "nodeType": "output",
                    "fromOp": 66,
                    "type": "string",
                    "id": "4215114193912975",
                },
                {"name": "artifactAlias-alias", "inputs": {"artifactAlias": 67}},
                {"nodeType": "var", "type": "artifactAlias", "varName": "row"},
                {
                    "nodeType": "output",
                    "fromOp": 69,
                    "type": "string",
                    "id": "711490887110080",
                },
                {"name": "artifact-name", "inputs": {"artifact": 70}},
                {
                    "nodeType": "output",
                    "fromOp": 71,
                    "type": "artifact",
                    "id": "2074339555347020",
                },
                {"name": "artifactAlias-artifact", "inputs": {"artifactAlias": 67}},
                {
                    "nodeType": "output",
                    "fromOp": 73,
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
                        "value": "string",
                    },
                    "id": "3549685395095410",
                },
                {"name": "artifactVersion-id", "inputs": {"artifactVersion": 74}},
                {
                    "nodeType": "output",
                    "fromOp": 75,
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
                    "id": "4143584412185738",
                },
                {
                    "name": "artifactMembership-artifactVersion",
                    "inputs": {"artifactMembership": 8},
                },
                {
                    "nodeType": "output",
                    "fromOp": 77,
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
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "alias": "string",
                                    "artifactCollectionName": "string",
                                },
                            },
                        },
                    },
                    "id": "3558086501874671",
                },
                {"name": "map", "inputs": {"arr": 78, "mapFn": 62}},
                {
                    "nodeType": "output",
                    "fromOp": 79,
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
                        "value": {"type": "list", "objectType": "artifactAlias"},
                    },
                    "id": "4609753332738093",
                },
                {
                    "name": "artifactMembership-aliases",
                    "inputs": {"artifactMembership": 8},
                },
                {
                    "nodeType": "output",
                    "fromOp": 81,
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
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "alias": "string",
                                    "artifactCollectionName": "string",
                                },
                            },
                        },
                    },
                    "id": "455925728986190",
                },
                {"name": "map", "inputs": {"arr": 82, "mapFn": 62}},
                {
                    "nodeType": "output",
                    "fromOp": 83,
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
                        "value": {"type": "list", "objectType": "artifactAlias"},
                    },
                    "id": "556778200112672",
                },
                {
                    "name": "artifactVersion-aliases",
                    "inputs": {"artifactVersion": 74, "hideVersions": 84},
                },
                {"nodeType": "const", "type": "boolean", "val": True},
                {
                    "nodeType": "output",
                    "fromOp": 86,
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
                        "value": {"type": "list", "objectType": "artifactMembership"},
                    },
                    "id": "5937444391107259",
                },
                {
                    "name": "artifactVersion-memberships",
                    "inputs": {"artifactVersion": 74},
                },
                {
                    "nodeType": "output",
                    "fromOp": 88,
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
                        "value": "boolean",
                    },
                    "id": "7854043332320847",
                },
                {"name": "artifact-isPortfolio", "inputs": {"artifact": 46}},
                {
                    "nodeType": "output",
                    "fromOp": 90,
                    "type": {
                        "type": "union",
                        "members": [
                            {
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
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                },
                                "value": "link",
                            },
                        ],
                    },
                    "id": "7151575090315146",
                },
                {"name": "none-coalesce", "inputs": {"lhs": 91, "rhs": 97}},
                {
                    "nodeType": "output",
                    "fromOp": 92,
                    "type": {
                        "type": "union",
                        "members": [
                            {
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
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                },
                                "value": "link",
                            },
                        ],
                    },
                    "id": "7713948407334268",
                },
                {"name": "run-link", "inputs": {"run": 93}},
                {
                    "nodeType": "output",
                    "fromOp": 94,
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
                        "value": {"type": "union", "members": ["none", "run"]},
                    },
                    "id": "8170865822461107",
                },
                {
                    "name": "artifactVersion-createdBy",
                    "inputs": {"artifactVersion": 95},
                },
                {
                    "nodeType": "output",
                    "fromOp": 96,
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
                    "id": "4143584412185738",
                },
                {
                    "name": "artifactMembership-artifactVersion",
                    "inputs": {"artifactMembership": 8},
                },
                {
                    "nodeType": "output",
                    "fromOp": 98,
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
                        "value": {"type": "union", "members": ["none", "link"]},
                    },
                    "id": "2463228004162593",
                },
                {"name": "user-link", "inputs": {"user": 99}},
                {
                    "nodeType": "output",
                    "fromOp": 100,
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
                        "value": {"type": "union", "members": ["none", "user"]},
                    },
                    "id": "7600134575140208",
                },
                {
                    "name": "artifactVersion-createdByUser",
                    "inputs": {"artifactVersion": 95},
                },
                {
                    "nodeType": "output",
                    "fromOp": 102,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {"entityName": "string"},
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {"project": "project"},
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"entity": "entity"},
                                            },
                                        },
                                        "value": "string",
                                    },
                                    "projectName": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                        "value": "string",
                                    },
                                    "artifactCollectionName": "string",
                                    "artifactCollectionAliases": {
                                        "type": "list",
                                        "objectType": "string",
                                        "maxLength": 30,
                                    },
                                    "artifactTypeName": {
                                        "type": "union",
                                        "members": ["none", "string"],
                                    },
                                    "artifactCollectionId": "string",
                                },
                            },
                        },
                    },
                    "id": "7403938026382942",
                },
                {"name": "map", "inputs": {"arr": 103, "mapFn": 119}},
                {
                    "nodeType": "output",
                    "fromOp": 104,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {"entityName": "string"},
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": {"type": "list", "objectType": "artifact"},
                    },
                    "id": "1724020081265161",
                },
                {"name": "filter", "inputs": {"arr": 105, "filterFn": 110}},
                {
                    "nodeType": "output",
                    "fromOp": 106,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {"entityName": "string"},
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": {"type": "list", "objectType": "artifact"},
                    },
                    "id": "2023184293210644",
                },
                {"name": "entity-portfolios", "inputs": {"entity": 107}},
                {
                    "nodeType": "output",
                    "fromOp": 108,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"entityName": "string"},
                        },
                        "value": "entity",
                    },
                    "id": "3338545190432492",
                },
                {"name": "root-entity", "inputs": {"entityName": 109}},
                {"nodeType": "const", "type": "string", "val": "timssweeney"},
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifact"},
                        "outputType": {"type": "union", "members": ["none", "boolean"]},
                    },
                    "val": {"nodeType": "output", "fromOp": 112},
                },
                {
                    "nodeType": "output",
                    "fromOp": 112,
                    "type": {"type": "union", "members": ["none", "boolean"]},
                    "id": "7284093421646659",
                },
                {"name": "string-equal", "inputs": {"lhs": 113, "rhs": 118}},
                {
                    "nodeType": "output",
                    "fromOp": 114,
                    "type": {"type": "union", "members": ["none", "string"]},
                    "id": "3757465892811307",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 115}},
                {
                    "nodeType": "output",
                    "fromOp": 116,
                    "type": {"type": "union", "members": ["none", "artifactType"]},
                    "id": "4045941319649867",
                },
                {"name": "artifact-type", "inputs": {"artifact": 117}},
                {"nodeType": "var", "type": "artifact", "varName": "row"},
                {"nodeType": "const", "type": "string", "val": "run_table"},
                {
                    "nodeType": "const",
                    "type": {
                        "type": "function",
                        "inputTypes": {"row": "artifact"},
                        "outputType": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "entityName": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {"project": "project"},
                                        },
                                        "value": {
                                            "type": "typedDict",
                                            "propertyTypes": {"entity": "entity"},
                                        },
                                    },
                                    "value": "string",
                                },
                                "projectName": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                    "value": "string",
                                },
                                "artifactCollectionName": "string",
                                "artifactCollectionAliases": {
                                    "type": "list",
                                    "objectType": "string",
                                    "maxLength": 30,
                                },
                                "artifactTypeName": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                                "artifactCollectionId": "string",
                            },
                        },
                    },
                    "val": {"nodeType": "output", "fromOp": 121},
                },
                {
                    "nodeType": "output",
                    "fromOp": 121,
                    "type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "entityName": {
                                "type": "tagged",
                                "tag": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"project": "project"},
                                    },
                                    "value": {
                                        "type": "typedDict",
                                        "propertyTypes": {"entity": "entity"},
                                    },
                                },
                                "value": "string",
                            },
                            "projectName": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                                "value": "string",
                            },
                            "artifactCollectionName": "string",
                            "artifactCollectionAliases": {
                                "type": "list",
                                "objectType": "string",
                                "maxLength": 30,
                            },
                            "artifactTypeName": {
                                "type": "union",
                                "members": ["none", "string"],
                            },
                            "artifactCollectionId": "string",
                        },
                    },
                    "id": "6049336463140620",
                },
                {
                    "name": "dict",
                    "inputs": {
                        "entityName": 122,
                        "projectName": 129,
                        "artifactCollectionName": 131,
                        "artifactCollectionAliases": 133,
                        "artifactTypeName": 140,
                        "artifactCollectionId": 144,
                    },
                },
                {
                    "nodeType": "output",
                    "fromOp": 123,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {"project": "project"},
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {"entity": "entity"},
                            },
                        },
                        "value": "string",
                    },
                    "id": "8774612696788142",
                },
                {"name": "entity-name", "inputs": {"entity": 124}},
                {
                    "nodeType": "output",
                    "fromOp": 125,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"project": "project"},
                        },
                        "value": "entity",
                    },
                    "id": "8748009072814723",
                },
                {"name": "project-entity", "inputs": {"project": 126}},
                {
                    "nodeType": "output",
                    "fromOp": 127,
                    "type": "project",
                    "id": "2437352500364524",
                },
                {"name": "artifact-project", "inputs": {"artifact": 128}},
                {"nodeType": "var", "type": "artifact", "varName": "row"},
                {
                    "nodeType": "output",
                    "fromOp": 130,
                    "type": {
                        "type": "tagged",
                        "tag": {
                            "type": "typedDict",
                            "propertyTypes": {"project": "project"},
                        },
                        "value": "string",
                    },
                    "id": "2305183914378038",
                },
                {"name": "project-name", "inputs": {"project": 126}},
                {
                    "nodeType": "output",
                    "fromOp": 132,
                    "type": "string",
                    "id": "2836867465098471",
                },
                {"name": "artifact-name", "inputs": {"artifact": 128}},
                {
                    "nodeType": "output",
                    "fromOp": 134,
                    "type": {"type": "list", "objectType": "string", "maxLength": 30},
                    "id": "7563365839301390",
                },
                {"name": "limit", "inputs": {"arr": 135, "limit": 139}},
                {
                    "nodeType": "output",
                    "fromOp": 136,
                    "type": {"type": "list", "objectType": "string"},
                    "id": "1316330603622919",
                },
                {"name": "artifactAlias-alias", "inputs": {"artifactAlias": 137}},
                {
                    "nodeType": "output",
                    "fromOp": 138,
                    "type": {"type": "list", "objectType": "artifactAlias"},
                    "id": "8296941764951998",
                },
                {"name": "artifact-aliases", "inputs": {"artifact": 128}},
                {"nodeType": "const", "type": "number", "val": 30},
                {
                    "nodeType": "output",
                    "fromOp": 141,
                    "type": {"type": "union", "members": ["none", "string"]},
                    "id": "3757465892811307",
                },
                {"name": "artifactType-name", "inputs": {"artifactType": 142}},
                {
                    "nodeType": "output",
                    "fromOp": 143,
                    "type": {"type": "union", "members": ["none", "artifactType"]},
                    "id": "4045941319649867",
                },
                {"name": "artifact-type", "inputs": {"artifact": 128}},
                {
                    "nodeType": "output",
                    "fromOp": 145,
                    "type": "string",
                    "id": "3972506126599560",
                },
                {"name": "artifact-id", "inputs": {"artifact": 128}},
            ],
            "rootNodes": [0, 18, 22, 42, 89, 101],
        }
    },
]
