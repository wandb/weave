from .. import ops as ops
from .. import weave_types as types
from ..ops_domain import wb_domain_types as wdt

from ..ops_domain.project_ops import root_all_projects
from ..ops_domain.report_ops import root_all_reports

from .. import compile
from ..language_features.tagging.tagged_value_type import TaggedValueType

from .. import api as weave

from .test_wb import table_mock1_no_display_name


def test_gql_compilation_with_keys():
    project_node = ops.project("stacey", "mendeleev")
    runs_node = project_node.runs()
    cell_node = runs_node.limit(1).id()
    compiled_node = compile.compile([cell_node])[0]

    run_type_keys = types.TypedDict(
        property_types={
            "id": types.String(),
            "name": types.String(),
        }
    )

    run_edges_type = types.TypedDict(
        property_types={
            "edges": types.List(
                object_type=types.TypedDict(property_types={"node": run_type_keys})
            )
        }
    )

    expected = TaggedValueType(
        types.TypedDict(
            {
                "project": wdt.ProjectType.with_keys(
                    {
                        "id": types.String(),
                        "name": types.String(),
                        "runs_c1233b7003317090ab5e2a75db4ad965": run_edges_type,
                    }
                )
            }
        ),
        types.List(
            TaggedValueType(
                types.TypedDict(
                    {"run": wdt.RunType.with_keys(run_type_keys.property_types)}
                ),
                types.String(),
            )
        ),
    )

    assert compiled_node.type == expected


def test_gql_compilation_root_op_custom_key_fn():
    root = root_all_projects().limit(1)[0].runs().id()
    compiled_node = compile.compile([root])[0]

    run_type = wdt.RunType.with_keys({"id": types.String(), "name": types.String()})
    project_type = wdt.ProjectType.with_keys(
        {
            "id": types.String(),
            "name": types.String(),
            "runs_c1233b7003317090ab5e2a75db4ad965": types.TypedDict(
                {
                    "edges": types.List(
                        types.TypedDict({"node": types.TypedDict(run_type.keys)})
                    )
                }
            ),
        }
    )

    expected = TaggedValueType(
        types.TypedDict({"project": project_type}),
        types.List(TaggedValueType(types.TypedDict({"run": run_type}), types.String())),
    )

    assert compiled_node.type == expected


def test_project_artifacts():
    node = ops.project("stacey", "mendeleev").artifacts().id()
    compiled_node = compile.compile([node])[0]
    expected = TaggedValueType(
        types.TypedDict(
            {
                "project": wdt.ProjectType.with_keys(
                    {
                        "id": types.String(),
                        "name": types.String(),
                        "artifactTypes_100": types.TypedDict(
                            {
                                "edges": types.List(
                                    types.TypedDict(
                                        {
                                            "node": types.TypedDict(
                                                {
                                                    "id": types.String(),
                                                    "artifactCollections_100": types.TypedDict(
                                                        {
                                                            "edges": types.List(
                                                                types.TypedDict(
                                                                    {
                                                                        "node": types.TypedDict(
                                                                            {
                                                                                "id": types.String(),
                                                                                "name": types.String(),
                                                                            }
                                                                        )
                                                                    }
                                                                )
                                                            )
                                                        }
                                                    ),
                                                }
                                            )
                                        }
                                    )
                                )
                            }
                        ),
                    }
                )
            }
        ),
        types.List(types.String()),
    )

    assert compiled_node.type == expected


def test_typename():
    node = ops.project("stacey", "mendeleev").artifacts()[0].isPortfolio()
    compiled_node = compile.compile([node])[0]
    expected = TaggedValueType(
        types.TypedDict(
            {
                "project": wdt.ProjectType.with_keys(
                    {
                        "id": types.String(),
                        "name": types.String(),
                        "artifactTypes_100": types.TypedDict(
                            {
                                "edges": types.List(
                                    types.TypedDict(
                                        {
                                            "node": types.TypedDict(
                                                {
                                                    "id": types.String(),
                                                    "artifactCollections_100": types.TypedDict(
                                                        {
                                                            "edges": types.List(
                                                                types.TypedDict(
                                                                    {
                                                                        "node": types.TypedDict(
                                                                            {
                                                                                "__typename": types.Const(
                                                                                    types.String(),
                                                                                    "ArtifactCollection",
                                                                                ),
                                                                                "id": types.String(),
                                                                                "name": types.String(),
                                                                            }
                                                                        )
                                                                    }
                                                                )
                                                            )
                                                        }
                                                    ),
                                                }
                                            )
                                        }
                                    )
                                )
                            }
                        ),
                    }
                )
            }
        ),
        types.Boolean(),
    )

    assert compiled_node.type == expected


def test_last_membership():
    node = ops.project("stacey", "mendeleev").artifacts()[0].lastMembership()
    compiled_node = compile.compile([node])[0]
    expected = TaggedValueType(
        types.TypedDict(
            {
                "project": wdt.ProjectType.with_keys(
                    {
                        "id": types.String(),
                        "name": types.String(),
                        "artifactTypes_100": types.TypedDict(
                            {
                                "edges": types.List(
                                    types.TypedDict(
                                        {
                                            "node": types.TypedDict(
                                                {
                                                    "id": types.String(),
                                                    "artifactCollections_100": types.TypedDict(
                                                        {
                                                            "edges": types.List(
                                                                types.TypedDict(
                                                                    {
                                                                        "node": types.TypedDict(
                                                                            {
                                                                                "id": types.String(),
                                                                                "name": types.String(),
                                                                                "artifactMemberships_first_1": types.TypedDict(
                                                                                    {
                                                                                        "edges": types.List(
                                                                                            types.TypedDict(
                                                                                                {
                                                                                                    "node": types.TypedDict(
                                                                                                        {
                                                                                                            "id": types.String(),
                                                                                                        }
                                                                                                    )
                                                                                                }
                                                                                            )
                                                                                        )
                                                                                    }
                                                                                ),
                                                                            }
                                                                        )
                                                                    }
                                                                )
                                                            )
                                                        }
                                                    ),
                                                }
                                            )
                                        }
                                    )
                                )
                            }
                        ),
                    }
                )
            }
        ),
        types.optional(
            wdt.ArtifactCollectionMembershipType.with_keys({"id": types.String()})
        ),
    )

    assert compiled_node.type == expected


def test_mapped_last_membership():
    node = ops.project("stacey", "mendeleev").artifacts().lastMembership()
    compiled_node = compile.compile([node])[0]
    expected = TaggedValueType(
        types.TypedDict(
            {
                "project": wdt.ProjectType.with_keys(
                    {
                        "id": types.String(),
                        "name": types.String(),
                        "artifactTypes_100": types.TypedDict(
                            {
                                "edges": types.List(
                                    types.TypedDict(
                                        {
                                            "node": types.TypedDict(
                                                {
                                                    "id": types.String(),
                                                    "artifactCollections_100": types.TypedDict(
                                                        {
                                                            "edges": types.List(
                                                                types.TypedDict(
                                                                    {
                                                                        "node": types.TypedDict(
                                                                            {
                                                                                "id": types.String(),
                                                                                "name": types.String(),
                                                                                "artifactMemberships_first_1": types.TypedDict(
                                                                                    {
                                                                                        "edges": types.List(
                                                                                            types.TypedDict(
                                                                                                {
                                                                                                    "node": types.TypedDict(
                                                                                                        {
                                                                                                            "id": types.String(),
                                                                                                        }
                                                                                                    )
                                                                                                }
                                                                                            )
                                                                                        )
                                                                                    }
                                                                                ),
                                                                            }
                                                                        )
                                                                    }
                                                                )
                                                            )
                                                        }
                                                    ),
                                                }
                                            )
                                        }
                                    )
                                )
                            }
                        ),
                    }
                )
            }
        ),
        types.List(
            types.optional(
                wdt.ArtifactCollectionMembershipType.with_keys({"id": types.String()})
            )
        ),
    )

    assert compiled_node.type == expected


def test_op_with_refiner(fake_wandb):
    fake_wandb.fake_api.add_mock(table_mock1_no_display_name)
    node = ops.project("stacey", "mendeleev").runs()[0].summary()["legacy_table"]
    compiled_node = compile.compile([node])[0]

    # it was hard to manually construct the type here in python, so i dumped it to
    # a dict in the debugger and re-created the type from that below :).
    expected_compiled_type_dict = {
        "type": "tagged",
        "tag": {
            "type": "typedDict",
            "propertyTypes": {
                "run": {
                    "type": "tagged",
                    "tag": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "project": {
                                "type": "GQLHasKeys",
                                "keys": {
                                    "id": "string",
                                    "name": "string",
                                    "runs_c1233b7003317090ab5e2a75db4ad965": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "edges": {
                                                "type": "list",
                                                "objectType": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "node": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "id": "string",
                                                                "name": "string",
                                                                "project": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "id": "string",
                                                                        "name": "string",
                                                                        "entity": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "id": "string",
                                                                                "name": "string",
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                                "summaryMetricsSubset": "string",
                                                            },
                                                        }
                                                    },
                                                },
                                            }
                                        },
                                    },
                                },
                                "keyless_weave_type_class": "project",
                            }
                        },
                    },
                    "value": {
                        "type": "GQLHasKeys",
                        "keys": {
                            "id": "string",
                            "name": "string",
                            "project": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "id": "string",
                                    "name": "string",
                                    "entity": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "id": "string",
                                            "name": "string",
                                        },
                                    },
                                },
                            },
                            "summaryMetricsSubset": "string",
                        },
                        "keyless_weave_type_class": "run",
                    },
                },
                "project": {
                    "type": "GQLHasKeys",
                    "keys": {
                        "id": "string",
                        "name": "string",
                        "runs_c1233b7003317090ab5e2a75db4ad965": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "edges": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "node": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "id": "string",
                                                    "name": "string",
                                                    "summaryMetricsSubset": {
                                                        "type": "union",
                                                        "members": ["none", "string"],
                                                    },
                                                    "project": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "id": "string",
                                                            "name": "string",
                                                            "entity": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "id": "string",
                                                                    "name": "string",
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                            }
                                        },
                                    },
                                }
                            },
                        },
                    },
                    "keyless_weave_type_class": "project",
                },
            },
        },
        "value": {
            "type": "file",
            "_base_type": {"type": "FileBase"},
            "extension": "json",
            "wbObjectType": {
                "type": "table",
                "_base_type": {"type": "Object"},
                "_is_object": True,
                "_rows": {
                    "type": "ArrowWeaveList",
                    "_base_type": {"type": "list"},
                    "objectType": {"type": "typedDict", "propertyTypes": {}},
                },
            },
        },
    }

    expected = types.TypeRegistry.type_from_dict(expected_compiled_type_dict)
    assert compiled_node.type == expected


def test_gql_connection_op():
    node = ops.project("stacey", "mendeleev").artifactTypes()[0].artifactVersions()
    compiled_node = compile.compile([node])[0]

    expected_compiled_type_dict = {
        "type": "tagged",
        "tag": {
            "type": "typedDict",
            "propertyTypes": {
                "project": {
                    "type": "GQLHasKeys",
                    "keys": {
                        "id": "string",
                        "name": "string",
                        "artifactTypes": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "edges": {
                                    "type": "list",
                                    "objectType": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "node": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "id": "string",
                                                    "name": "string",
                                                    "artifactCollections_c1233b7003317090ab5e2a75db4ad965": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "edges": {
                                                                "type": "list",
                                                                "objectType": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "node": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "artifacts_c1233b7003317090ab5e2a75db4ad965": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "edges": {
                                                                                            "type": "list",
                                                                                            "objectType": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "node": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "id": "string"
                                                                                                        },
                                                                                                    }
                                                                                                },
                                                                                            },
                                                                                        }
                                                                                    },
                                                                                }
                                                                            },
                                                                        }
                                                                    },
                                                                },
                                                            }
                                                        },
                                                    },
                                                },
                                            }
                                        },
                                    },
                                }
                            },
                        },
                    },
                    "keyless_weave_type_class": "project",
                }
            },
        },
        "value": {
            "type": "GQLHasKeys",
            "keys": {"id": "string"},
            "keyless_weave_type_class": "artifactVersion",
        },
    }

    expected = types.TypeRegistry.type_from_dict(expected_compiled_type_dict)

    assert compiled_node.type == expected


def test_early_termination_of_gql_key_propagation(fake_wandb):
    # this test checks to make sure that if we encounter an op that does not
    # have a GQL key prop fn defined, it still executes and we can still
    # serialize and deserialize the result, even though we dont have the
    # keys for the result

    fake_wandb.fake_api.add_mock(
        lambda query, idx: {
            "instance": {
                "views_500": {
                    "edges": [
                        {
                            "node": {
                                "type": "runs",
                                "id": "c1233b7003317090ab5e2a75db4ad965",
                                "project": {
                                    "id": "e1233b7003317090ab5e2a75db4ad965",
                                    "name": "test-project-1",
                                },
                            }
                        }
                    ]
                }
            }
        }
    )

    # all reports has not been migrated yet
    projects_node = root_all_reports().project()

    # these projects should not have keys because root_all_reports() does not return a HasKeys type
    assert projects_node.type == types.List(wdt.ProjectType)

    projects = weave.use(projects_node)
    assert len(projects) == 1

    # keys are picked back up when we convert a literal to a constnode
    # and call type_of on it

    # convert projects to a constnode and call typeof on it to get its type (and keys)
    names_node = ops.project_ops.name(projects)

    # compile because we need to run dispatch to use the right op (mapped project-name)
    # because it wont be dispatched above (the above graph is not executable as is)
    names_node = compile.compile([names_node])[0]

    assert names_node.type == types.List(
        TaggedValueType(
            types.TypedDict(
                {
                    "project": wdt.ProjectType.with_keys(
                        {"id": types.String(), "name": types.String()}
                    )
                }
            ),
            types.String(),
        )
    )

    names = weave.use(names_node)
    assert names[0] == "test-project-1"
