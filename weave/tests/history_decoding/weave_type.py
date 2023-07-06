weave_type = {
    "type": "list",
    "objectType": {
        "type": "typedDict",
        "propertyTypes": {
            "string_key": "string",
            "bool_key": "boolean",
            "number_key": "int",
            "none_key": "none",
            "custom_1": {
                "type": "typedDict",
                "propertyTypes": {
                    "_type": "string",
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "type": "string",
                            "propertyTypes": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "type": "string",
                                            "propertyTypes": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "string",
                                                    "number_key": "string",
                                                    "none_key": "string",
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                        },
                    },
                    "_val": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                        },
                    },
                },
            },
            "list_data_uniform_2": {
                "type": "list",
                "objectType": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "string_key": "string",
                        "bool_key": "boolean",
                        "number_key": "int",
                        "none_key": "none",
                        "custom_1": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "_type": "string",
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "type": "string",
                                        "propertyTypes": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "a": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "string",
                                                                "number_key": "string",
                                                                "none_key": "string",
                                                            },
                                                        },
                                                    },
                                                }
                                            },
                                        },
                                    },
                                },
                                "_val": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "list_data_mixed_2": {
                "type": "list",
                "objectType": {
                    "type": "union",
                    "members": [
                        {
                            "type": "typedDict",
                            "propertyTypes": {
                                "bool_key": {
                                    "type": "union",
                                    "members": ["boolean", "none"],
                                },
                                "number_key": {
                                    "type": "union",
                                    "members": ["int", "none"],
                                },
                                "none_key": "none",
                                "custom_1": {
                                    "type": "union",
                                    "members": [
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "_type": "string",
                                                "_weave_type": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "a": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "string",
                                                                                "number_key": "string",
                                                                                "none_key": "string",
                                                                            },
                                                                        },
                                                                    },
                                                                }
                                                            },
                                                        },
                                                    },
                                                },
                                                "_val": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "string_key": "string",
                                                        "bool_key": "boolean",
                                                        "number_key": "int",
                                                        "none_key": "none",
                                                    },
                                                },
                                            },
                                        },
                                        "none",
                                    ],
                                },
                                "string_key": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                                "_type": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                                "_weave_type": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "type": "string",
                                                "propertyTypes": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "a": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "string_key": "string",
                                                                        "bool_key": "string",
                                                                        "number_key": "string",
                                                                        "none_key": "string",
                                                                    },
                                                                },
                                                            },
                                                        }
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                                "_val": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                        "string",
                        "boolean",
                        "int",
                        "none",
                    ],
                },
            },
            "dict_data_2": {
                "type": "typedDict",
                "propertyTypes": {
                    "string_key": "string",
                    "bool_key": "boolean",
                    "number_key": "int",
                    "none_key": "none",
                    "custom_1": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "_type": "string",
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "type": "string",
                                    "propertyTypes": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "type": "string",
                                                    "propertyTypes": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "string_key": "string",
                                                            "bool_key": "string",
                                                            "number_key": "string",
                                                            "none_key": "string",
                                                        },
                                                    },
                                                },
                                            }
                                        },
                                    },
                                },
                            },
                            "_val": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            },
                        },
                    },
                },
            },
            "custom_3": {
                "type": "typedDict",
                "propertyTypes": {
                    "_type": "string",
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "type": "string",
                            "propertyTypes": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "type": "string",
                                            "propertyTypes": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "string",
                                                    "number_key": "string",
                                                    "none_key": "string",
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                        },
                    },
                    "_val": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                            "custom_1": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "_type": "string",
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "type": "string",
                                            "propertyTypes": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "a": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "type": "string",
                                                            "propertyTypes": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "string_key": "string",
                                                                    "bool_key": "string",
                                                                    "number_key": "string",
                                                                    "none_key": "string",
                                                                },
                                                            },
                                                        },
                                                    }
                                                },
                                            },
                                        },
                                    },
                                    "_val": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    },
                                },
                            },
                            "list_data_uniform_2": {
                                "type": "list",
                                "objectType": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                        "custom_1": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "_type": "string",
                                                "_weave_type": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "a": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "string",
                                                                                "number_key": "string",
                                                                                "none_key": "string",
                                                                            },
                                                                        },
                                                                    },
                                                                }
                                                            },
                                                        },
                                                    },
                                                },
                                                "_val": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "string_key": "string",
                                                        "bool_key": "boolean",
                                                        "number_key": "int",
                                                        "none_key": "none",
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                            "list_data_mixed_2": {
                                "type": "list",
                                "objectType": {
                                    "type": "union",
                                    "members": [
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "bool_key": {
                                                    "type": "union",
                                                    "members": ["boolean", "none"],
                                                },
                                                "number_key": {
                                                    "type": "union",
                                                    "members": ["int", "none"],
                                                },
                                                "none_key": "none",
                                                "custom_1": {
                                                    "type": "union",
                                                    "members": [
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "_type": "string",
                                                                "_weave_type": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "a": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "type": "string",
                                                                                        "propertyTypes": {
                                                                                            "type": "typedDict",
                                                                                            "propertyTypes": {
                                                                                                "string_key": "string",
                                                                                                "bool_key": "string",
                                                                                                "number_key": "string",
                                                                                                "none_key": "string",
                                                                                            },
                                                                                        },
                                                                                    },
                                                                                }
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                                "_val": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "string_key": "string",
                                                                        "bool_key": "boolean",
                                                                        "number_key": "int",
                                                                        "none_key": "none",
                                                                    },
                                                                },
                                                            },
                                                        },
                                                        "none",
                                                    ],
                                                },
                                                "string_key": {
                                                    "type": "union",
                                                    "members": ["none", "string"],
                                                },
                                                "_type": {
                                                    "type": "union",
                                                    "members": ["none", "string"],
                                                },
                                                "_weave_type": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "a": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "type": "string",
                                                                                "propertyTypes": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "string_key": "string",
                                                                                        "bool_key": "string",
                                                                                        "number_key": "string",
                                                                                        "none_key": "string",
                                                                                    },
                                                                                },
                                                                            },
                                                                        }
                                                                    },
                                                                },
                                                            },
                                                        },
                                                    ],
                                                },
                                                "_val": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "boolean",
                                                                "number_key": "int",
                                                                "none_key": "none",
                                                            },
                                                        },
                                                    ],
                                                },
                                            },
                                        },
                                        "string",
                                        "boolean",
                                        "int",
                                        "none",
                                    ],
                                },
                            },
                            "dict_data_2": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                    "custom_1": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_type": "string",
                                            "_weave_type": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "type": "string",
                                                    "propertyTypes": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "a": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "type": "string",
                                                                    "propertyTypes": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "string_key": "string",
                                                                            "bool_key": "string",
                                                                            "number_key": "string",
                                                                            "none_key": "string",
                                                                        },
                                                                    },
                                                                },
                                                            }
                                                        },
                                                    },
                                                },
                                            },
                                            "_val": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "list_data_uniform_4": {
                "type": "list",
                "objectType": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "string_key": "string",
                        "bool_key": "boolean",
                        "number_key": "int",
                        "none_key": "none",
                        "custom_1": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "_type": "string",
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "type": "string",
                                        "propertyTypes": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "a": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "string",
                                                                "number_key": "string",
                                                                "none_key": "string",
                                                            },
                                                        },
                                                    },
                                                }
                                            },
                                        },
                                    },
                                },
                                "_val": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                },
                            },
                        },
                        "list_data_uniform_2": {
                            "type": "list",
                            "objectType": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                    "custom_1": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_type": "string",
                                            "_weave_type": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "type": "string",
                                                    "propertyTypes": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "a": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "type": "string",
                                                                    "propertyTypes": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "string_key": "string",
                                                                            "bool_key": "string",
                                                                            "number_key": "string",
                                                                            "none_key": "string",
                                                                        },
                                                                    },
                                                                },
                                                            }
                                                        },
                                                    },
                                                },
                                            },
                                            "_val": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "list_data_mixed_2": {
                            "type": "list",
                            "objectType": {
                                "type": "union",
                                "members": [
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "bool_key": {
                                                "type": "union",
                                                "members": ["boolean", "none"],
                                            },
                                            "number_key": {
                                                "type": "union",
                                                "members": ["int", "none"],
                                            },
                                            "none_key": "none",
                                            "custom_1": {
                                                "type": "union",
                                                "members": [
                                                    {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "_type": "string",
                                                            "_weave_type": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "type": "string",
                                                                    "propertyTypes": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "a": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "type": "string",
                                                                                    "propertyTypes": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "string_key": "string",
                                                                                            "bool_key": "string",
                                                                                            "number_key": "string",
                                                                                            "none_key": "string",
                                                                                        },
                                                                                    },
                                                                                },
                                                                            }
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                            "_val": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "string_key": "string",
                                                                    "bool_key": "boolean",
                                                                    "number_key": "int",
                                                                    "none_key": "none",
                                                                },
                                                            },
                                                        },
                                                    },
                                                    "none",
                                                ],
                                            },
                                            "string_key": {
                                                "type": "union",
                                                "members": ["none", "string"],
                                            },
                                            "_type": {
                                                "type": "union",
                                                "members": ["none", "string"],
                                            },
                                            "_weave_type": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "type": "string",
                                                            "propertyTypes": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "a": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "type": "string",
                                                                            "propertyTypes": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "string_key": "string",
                                                                                    "bool_key": "string",
                                                                                    "number_key": "string",
                                                                                    "none_key": "string",
                                                                                },
                                                                            },
                                                                        },
                                                                    }
                                                                },
                                                            },
                                                        },
                                                    },
                                                ],
                                            },
                                            "_val": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "string_key": "string",
                                                            "bool_key": "boolean",
                                                            "number_key": "int",
                                                            "none_key": "none",
                                                        },
                                                    },
                                                ],
                                            },
                                        },
                                    },
                                    "string",
                                    "boolean",
                                    "int",
                                    "none",
                                ],
                            },
                        },
                        "dict_data_2": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                                "custom_1": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "_type": "string",
                                        "_weave_type": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "type": "string",
                                                "propertyTypes": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "a": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "string_key": "string",
                                                                        "bool_key": "string",
                                                                        "number_key": "string",
                                                                        "none_key": "string",
                                                                    },
                                                                },
                                                            },
                                                        }
                                                    },
                                                },
                                            },
                                        },
                                        "_val": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                        "custom_3": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "_type": "string",
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "type": "string",
                                        "propertyTypes": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "a": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "string",
                                                                "number_key": "string",
                                                                "none_key": "string",
                                                            },
                                                        },
                                                    },
                                                }
                                            },
                                        },
                                    },
                                },
                                "_val": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                        "custom_1": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "_type": "string",
                                                "_weave_type": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "a": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "string",
                                                                                "number_key": "string",
                                                                                "none_key": "string",
                                                                            },
                                                                        },
                                                                    },
                                                                }
                                                            },
                                                        },
                                                    },
                                                },
                                                "_val": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "string_key": "string",
                                                        "bool_key": "boolean",
                                                        "number_key": "int",
                                                        "none_key": "none",
                                                    },
                                                },
                                            },
                                        },
                                        "list_data_uniform_2": {
                                            "type": "list",
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                    "custom_1": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "_type": "string",
                                                            "_weave_type": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "type": "string",
                                                                    "propertyTypes": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "a": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "type": "string",
                                                                                    "propertyTypes": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "string_key": "string",
                                                                                            "bool_key": "string",
                                                                                            "number_key": "string",
                                                                                            "none_key": "string",
                                                                                        },
                                                                                    },
                                                                                },
                                                                            }
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                            "_val": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "string_key": "string",
                                                                    "bool_key": "boolean",
                                                                    "number_key": "int",
                                                                    "none_key": "none",
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        "list_data_mixed_2": {
                                            "type": "list",
                                            "objectType": {
                                                "type": "union",
                                                "members": [
                                                    {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "bool_key": {
                                                                "type": "union",
                                                                "members": [
                                                                    "boolean",
                                                                    "none",
                                                                ],
                                                            },
                                                            "number_key": {
                                                                "type": "union",
                                                                "members": [
                                                                    "int",
                                                                    "none",
                                                                ],
                                                            },
                                                            "none_key": "none",
                                                            "custom_1": {
                                                                "type": "union",
                                                                "members": [
                                                                    {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "_type": "string",
                                                                            "_weave_type": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "type": "string",
                                                                                    "propertyTypes": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "a": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "type": "string",
                                                                                                    "propertyTypes": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "string_key": "string",
                                                                                                            "bool_key": "string",
                                                                                                            "number_key": "string",
                                                                                                            "none_key": "string",
                                                                                                        },
                                                                                                    },
                                                                                                },
                                                                                            }
                                                                                        },
                                                                                    },
                                                                                },
                                                                            },
                                                                            "_val": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "string_key": "string",
                                                                                    "bool_key": "boolean",
                                                                                    "number_key": "int",
                                                                                    "none_key": "none",
                                                                                },
                                                                            },
                                                                        },
                                                                    },
                                                                    "none",
                                                                ],
                                                            },
                                                            "string_key": {
                                                                "type": "union",
                                                                "members": [
                                                                    "none",
                                                                    "string",
                                                                ],
                                                            },
                                                            "_type": {
                                                                "type": "union",
                                                                "members": [
                                                                    "none",
                                                                    "string",
                                                                ],
                                                            },
                                                            "_weave_type": {
                                                                "type": "union",
                                                                "members": [
                                                                    "none",
                                                                    {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "type": "string",
                                                                            "propertyTypes": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "a": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "type": "string",
                                                                                            "propertyTypes": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "string_key": "string",
                                                                                                    "bool_key": "string",
                                                                                                    "number_key": "string",
                                                                                                    "none_key": "string",
                                                                                                },
                                                                                            },
                                                                                        },
                                                                                    }
                                                                                },
                                                                            },
                                                                        },
                                                                    },
                                                                ],
                                                            },
                                                            "_val": {
                                                                "type": "union",
                                                                "members": [
                                                                    "none",
                                                                    {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "string_key": "string",
                                                                            "bool_key": "boolean",
                                                                            "number_key": "int",
                                                                            "none_key": "none",
                                                                        },
                                                                    },
                                                                ],
                                                            },
                                                        },
                                                    },
                                                    "string",
                                                    "boolean",
                                                    "int",
                                                    "none",
                                                ],
                                            },
                                        },
                                        "dict_data_2": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                                "custom_1": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "_type": "string",
                                                        "_weave_type": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "a": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "type": "string",
                                                                                "propertyTypes": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "string_key": "string",
                                                                                        "bool_key": "string",
                                                                                        "number_key": "string",
                                                                                        "none_key": "string",
                                                                                    },
                                                                                },
                                                                            },
                                                                        }
                                                                    },
                                                                },
                                                            },
                                                        },
                                                        "_val": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "boolean",
                                                                "number_key": "int",
                                                                "none_key": "none",
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "list_data_mixed_4": {
                "type": "list",
                "objectType": {
                    "type": "union",
                    "members": [
                        {
                            "type": "typedDict",
                            "propertyTypes": {
                                "bool_key": {
                                    "type": "union",
                                    "members": ["boolean", "none"],
                                },
                                "number_key": {
                                    "type": "union",
                                    "members": ["int", "none"],
                                },
                                "none_key": "none",
                                "custom_1": {
                                    "type": "union",
                                    "members": [
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "_type": "string",
                                                "_weave_type": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "a": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "string",
                                                                                "number_key": "string",
                                                                                "none_key": "string",
                                                                            },
                                                                        },
                                                                    },
                                                                }
                                                            },
                                                        },
                                                    },
                                                },
                                                "_val": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "string_key": "string",
                                                        "bool_key": "boolean",
                                                        "number_key": "int",
                                                        "none_key": "none",
                                                    },
                                                },
                                            },
                                        },
                                        "none",
                                    ],
                                },
                                "list_data_uniform_2": {
                                    "type": "union",
                                    "members": [
                                        {
                                            "type": "list",
                                            "objectType": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                    "custom_1": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "_type": "string",
                                                            "_weave_type": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "type": "string",
                                                                    "propertyTypes": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "a": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "type": "string",
                                                                                    "propertyTypes": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "string_key": "string",
                                                                                            "bool_key": "string",
                                                                                            "number_key": "string",
                                                                                            "none_key": "string",
                                                                                        },
                                                                                    },
                                                                                },
                                                                            }
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                            "_val": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "string_key": "string",
                                                                    "bool_key": "boolean",
                                                                    "number_key": "int",
                                                                    "none_key": "none",
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        "none",
                                    ],
                                },
                                "list_data_mixed_2": {
                                    "type": "union",
                                    "members": [
                                        {
                                            "type": "list",
                                            "objectType": {
                                                "type": "union",
                                                "members": [
                                                    {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "bool_key": {
                                                                "type": "union",
                                                                "members": [
                                                                    "boolean",
                                                                    "none",
                                                                ],
                                                            },
                                                            "number_key": {
                                                                "type": "union",
                                                                "members": [
                                                                    "int",
                                                                    "none",
                                                                ],
                                                            },
                                                            "none_key": "none",
                                                            "custom_1": {
                                                                "type": "union",
                                                                "members": [
                                                                    {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "_type": "string",
                                                                            "_weave_type": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "type": "string",
                                                                                    "propertyTypes": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "a": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "type": "string",
                                                                                                    "propertyTypes": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "string_key": "string",
                                                                                                            "bool_key": "string",
                                                                                                            "number_key": "string",
                                                                                                            "none_key": "string",
                                                                                                        },
                                                                                                    },
                                                                                                },
                                                                                            }
                                                                                        },
                                                                                    },
                                                                                },
                                                                            },
                                                                            "_val": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "string_key": "string",
                                                                                    "bool_key": "boolean",
                                                                                    "number_key": "int",
                                                                                    "none_key": "none",
                                                                                },
                                                                            },
                                                                        },
                                                                    },
                                                                    "none",
                                                                ],
                                                            },
                                                            "string_key": {
                                                                "type": "union",
                                                                "members": [
                                                                    "none",
                                                                    "string",
                                                                ],
                                                            },
                                                            "_type": {
                                                                "type": "union",
                                                                "members": [
                                                                    "none",
                                                                    "string",
                                                                ],
                                                            },
                                                            "_weave_type": {
                                                                "type": "union",
                                                                "members": [
                                                                    "none",
                                                                    {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "type": "string",
                                                                            "propertyTypes": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "a": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "type": "string",
                                                                                            "propertyTypes": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "string_key": "string",
                                                                                                    "bool_key": "string",
                                                                                                    "number_key": "string",
                                                                                                    "none_key": "string",
                                                                                                },
                                                                                            },
                                                                                        },
                                                                                    }
                                                                                },
                                                                            },
                                                                        },
                                                                    },
                                                                ],
                                                            },
                                                            "_val": {
                                                                "type": "union",
                                                                "members": [
                                                                    "none",
                                                                    {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "string_key": "string",
                                                                            "bool_key": "boolean",
                                                                            "number_key": "int",
                                                                            "none_key": "none",
                                                                        },
                                                                    },
                                                                ],
                                                            },
                                                        },
                                                    },
                                                    "string",
                                                    "boolean",
                                                    "int",
                                                    "none",
                                                ],
                                            },
                                        },
                                        "none",
                                    ],
                                },
                                "dict_data_2": {
                                    "type": "union",
                                    "members": [
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                                "custom_1": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "_type": "string",
                                                        "_weave_type": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "a": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "type": "string",
                                                                                "propertyTypes": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "string_key": "string",
                                                                                        "bool_key": "string",
                                                                                        "number_key": "string",
                                                                                        "none_key": "string",
                                                                                    },
                                                                                },
                                                                            },
                                                                        }
                                                                    },
                                                                },
                                                            },
                                                        },
                                                        "_val": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "boolean",
                                                                "number_key": "int",
                                                                "none_key": "none",
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        "none",
                                    ],
                                },
                                "custom_3": {
                                    "type": "union",
                                    "members": [
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "_type": "string",
                                                "_weave_type": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "a": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "string",
                                                                                "number_key": "string",
                                                                                "none_key": "string",
                                                                            },
                                                                        },
                                                                    },
                                                                }
                                                            },
                                                        },
                                                    },
                                                },
                                                "_val": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "string_key": "string",
                                                        "bool_key": "boolean",
                                                        "number_key": "int",
                                                        "none_key": "none",
                                                        "custom_1": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "_type": "string",
                                                                "_weave_type": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "a": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "type": "string",
                                                                                        "propertyTypes": {
                                                                                            "type": "typedDict",
                                                                                            "propertyTypes": {
                                                                                                "string_key": "string",
                                                                                                "bool_key": "string",
                                                                                                "number_key": "string",
                                                                                                "none_key": "string",
                                                                                            },
                                                                                        },
                                                                                    },
                                                                                }
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                                "_val": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "string_key": "string",
                                                                        "bool_key": "boolean",
                                                                        "number_key": "int",
                                                                        "none_key": "none",
                                                                    },
                                                                },
                                                            },
                                                        },
                                                        "list_data_uniform_2": {
                                                            "type": "list",
                                                            "objectType": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "string_key": "string",
                                                                    "bool_key": "boolean",
                                                                    "number_key": "int",
                                                                    "none_key": "none",
                                                                    "custom_1": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "_type": "string",
                                                                            "_weave_type": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "type": "string",
                                                                                    "propertyTypes": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "a": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "type": "string",
                                                                                                    "propertyTypes": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "string_key": "string",
                                                                                                            "bool_key": "string",
                                                                                                            "number_key": "string",
                                                                                                            "none_key": "string",
                                                                                                        },
                                                                                                    },
                                                                                                },
                                                                                            }
                                                                                        },
                                                                                    },
                                                                                },
                                                                            },
                                                                            "_val": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "string_key": "string",
                                                                                    "bool_key": "boolean",
                                                                                    "number_key": "int",
                                                                                    "none_key": "none",
                                                                                },
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                        },
                                                        "list_data_mixed_2": {
                                                            "type": "list",
                                                            "objectType": {
                                                                "type": "union",
                                                                "members": [
                                                                    {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "bool_key": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "boolean",
                                                                                    "none",
                                                                                ],
                                                                            },
                                                                            "number_key": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "int",
                                                                                    "none",
                                                                                ],
                                                                            },
                                                                            "none_key": "none",
                                                                            "custom_1": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "_type": "string",
                                                                                            "_weave_type": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "type": "string",
                                                                                                    "propertyTypes": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "a": {
                                                                                                                "type": "typedDict",
                                                                                                                "propertyTypes": {
                                                                                                                    "type": "string",
                                                                                                                    "propertyTypes": {
                                                                                                                        "type": "typedDict",
                                                                                                                        "propertyTypes": {
                                                                                                                            "string_key": "string",
                                                                                                                            "bool_key": "string",
                                                                                                                            "number_key": "string",
                                                                                                                            "none_key": "string",
                                                                                                                        },
                                                                                                                    },
                                                                                                                },
                                                                                                            }
                                                                                                        },
                                                                                                    },
                                                                                                },
                                                                                            },
                                                                                            "_val": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "string_key": "string",
                                                                                                    "bool_key": "boolean",
                                                                                                    "number_key": "int",
                                                                                                    "none_key": "none",
                                                                                                },
                                                                                            },
                                                                                        },
                                                                                    },
                                                                                    "none",
                                                                                ],
                                                                            },
                                                                            "string_key": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "none",
                                                                                    "string",
                                                                                ],
                                                                            },
                                                                            "_type": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "none",
                                                                                    "string",
                                                                                ],
                                                                            },
                                                                            "_weave_type": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "none",
                                                                                    {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "type": "string",
                                                                                            "propertyTypes": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "a": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "type": "string",
                                                                                                            "propertyTypes": {
                                                                                                                "type": "typedDict",
                                                                                                                "propertyTypes": {
                                                                                                                    "string_key": "string",
                                                                                                                    "bool_key": "string",
                                                                                                                    "number_key": "string",
                                                                                                                    "none_key": "string",
                                                                                                                },
                                                                                                            },
                                                                                                        },
                                                                                                    }
                                                                                                },
                                                                                            },
                                                                                        },
                                                                                    },
                                                                                ],
                                                                            },
                                                                            "_val": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "none",
                                                                                    {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "string_key": "string",
                                                                                            "bool_key": "boolean",
                                                                                            "number_key": "int",
                                                                                            "none_key": "none",
                                                                                        },
                                                                                    },
                                                                                ],
                                                                            },
                                                                        },
                                                                    },
                                                                    "string",
                                                                    "boolean",
                                                                    "int",
                                                                    "none",
                                                                ],
                                                            },
                                                        },
                                                        "dict_data_2": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "boolean",
                                                                "number_key": "int",
                                                                "none_key": "none",
                                                                "custom_1": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "_type": "string",
                                                                        "_weave_type": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "type": "string",
                                                                                "propertyTypes": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "a": {
                                                                                            "type": "typedDict",
                                                                                            "propertyTypes": {
                                                                                                "type": "string",
                                                                                                "propertyTypes": {
                                                                                                    "type": "typedDict",
                                                                                                    "propertyTypes": {
                                                                                                        "string_key": "string",
                                                                                                        "bool_key": "string",
                                                                                                        "number_key": "string",
                                                                                                        "none_key": "string",
                                                                                                    },
                                                                                                },
                                                                                            },
                                                                                        }
                                                                                    },
                                                                                },
                                                                            },
                                                                        },
                                                                        "_val": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "boolean",
                                                                                "number_key": "int",
                                                                                "none_key": "none",
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        "none",
                                    ],
                                },
                                "string_key": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                                "_type": {
                                    "type": "union",
                                    "members": ["none", "string"],
                                },
                                "_weave_type": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "type": "string",
                                                "propertyTypes": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "a": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "string_key": "string",
                                                                        "bool_key": "string",
                                                                        "number_key": "string",
                                                                        "none_key": "string",
                                                                    },
                                                                },
                                                            },
                                                        }
                                                    },
                                                },
                                            },
                                        },
                                    ],
                                },
                                "_val": {
                                    "type": "union",
                                    "members": [
                                        "none",
                                        {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                                "custom_1": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "_type": "string",
                                                                "_weave_type": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "a": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "type": "string",
                                                                                        "propertyTypes": {
                                                                                            "type": "typedDict",
                                                                                            "propertyTypes": {
                                                                                                "string_key": "string",
                                                                                                "bool_key": "string",
                                                                                                "number_key": "string",
                                                                                                "none_key": "string",
                                                                                            },
                                                                                        },
                                                                                    },
                                                                                }
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                                "_val": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "string_key": "string",
                                                                        "bool_key": "boolean",
                                                                        "number_key": "int",
                                                                        "none_key": "none",
                                                                    },
                                                                },
                                                            },
                                                        },
                                                    ],
                                                },
                                                "list_data_uniform_2": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        {
                                                            "type": "list",
                                                            "objectType": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "string_key": "string",
                                                                    "bool_key": "boolean",
                                                                    "number_key": "int",
                                                                    "none_key": "none",
                                                                    "custom_1": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "_type": "string",
                                                                            "_weave_type": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "type": "string",
                                                                                    "propertyTypes": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "a": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "type": "string",
                                                                                                    "propertyTypes": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "string_key": "string",
                                                                                                            "bool_key": "string",
                                                                                                            "number_key": "string",
                                                                                                            "none_key": "string",
                                                                                                        },
                                                                                                    },
                                                                                                },
                                                                                            }
                                                                                        },
                                                                                    },
                                                                                },
                                                                            },
                                                                            "_val": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "string_key": "string",
                                                                                    "bool_key": "boolean",
                                                                                    "number_key": "int",
                                                                                    "none_key": "none",
                                                                                },
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                        },
                                                    ],
                                                },
                                                "list_data_mixed_2": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        {
                                                            "type": "list",
                                                            "objectType": {
                                                                "type": "union",
                                                                "members": [
                                                                    {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "bool_key": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "boolean",
                                                                                    "none",
                                                                                ],
                                                                            },
                                                                            "number_key": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "int",
                                                                                    "none",
                                                                                ],
                                                                            },
                                                                            "none_key": "none",
                                                                            "custom_1": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "_type": "string",
                                                                                            "_weave_type": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "type": "string",
                                                                                                    "propertyTypes": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "a": {
                                                                                                                "type": "typedDict",
                                                                                                                "propertyTypes": {
                                                                                                                    "type": "string",
                                                                                                                    "propertyTypes": {
                                                                                                                        "type": "typedDict",
                                                                                                                        "propertyTypes": {
                                                                                                                            "string_key": "string",
                                                                                                                            "bool_key": "string",
                                                                                                                            "number_key": "string",
                                                                                                                            "none_key": "string",
                                                                                                                        },
                                                                                                                    },
                                                                                                                },
                                                                                                            }
                                                                                                        },
                                                                                                    },
                                                                                                },
                                                                                            },
                                                                                            "_val": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "string_key": "string",
                                                                                                    "bool_key": "boolean",
                                                                                                    "number_key": "int",
                                                                                                    "none_key": "none",
                                                                                                },
                                                                                            },
                                                                                        },
                                                                                    },
                                                                                    "none",
                                                                                ],
                                                                            },
                                                                            "string_key": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "none",
                                                                                    "string",
                                                                                ],
                                                                            },
                                                                            "_type": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "none",
                                                                                    "string",
                                                                                ],
                                                                            },
                                                                            "_weave_type": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "none",
                                                                                    {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "type": "string",
                                                                                            "propertyTypes": {
                                                                                                "type": "typedDict",
                                                                                                "propertyTypes": {
                                                                                                    "a": {
                                                                                                        "type": "typedDict",
                                                                                                        "propertyTypes": {
                                                                                                            "type": "string",
                                                                                                            "propertyTypes": {
                                                                                                                "type": "typedDict",
                                                                                                                "propertyTypes": {
                                                                                                                    "string_key": "string",
                                                                                                                    "bool_key": "string",
                                                                                                                    "number_key": "string",
                                                                                                                    "none_key": "string",
                                                                                                                },
                                                                                                            },
                                                                                                        },
                                                                                                    }
                                                                                                },
                                                                                            },
                                                                                        },
                                                                                    },
                                                                                ],
                                                                            },
                                                                            "_val": {
                                                                                "type": "union",
                                                                                "members": [
                                                                                    "none",
                                                                                    {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "string_key": "string",
                                                                                            "bool_key": "boolean",
                                                                                            "number_key": "int",
                                                                                            "none_key": "none",
                                                                                        },
                                                                                    },
                                                                                ],
                                                                            },
                                                                        },
                                                                    },
                                                                    "string",
                                                                    "boolean",
                                                                    "int",
                                                                    "none",
                                                                ],
                                                            },
                                                        },
                                                    ],
                                                },
                                                "dict_data_2": {
                                                    "type": "union",
                                                    "members": [
                                                        "none",
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "boolean",
                                                                "number_key": "int",
                                                                "none_key": "none",
                                                                "custom_1": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "_type": "string",
                                                                        "_weave_type": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "type": "string",
                                                                                "propertyTypes": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "a": {
                                                                                            "type": "typedDict",
                                                                                            "propertyTypes": {
                                                                                                "type": "string",
                                                                                                "propertyTypes": {
                                                                                                    "type": "typedDict",
                                                                                                    "propertyTypes": {
                                                                                                        "string_key": "string",
                                                                                                        "bool_key": "string",
                                                                                                        "number_key": "string",
                                                                                                        "none_key": "string",
                                                                                                    },
                                                                                                },
                                                                                            },
                                                                                        }
                                                                                    },
                                                                                },
                                                                            },
                                                                        },
                                                                        "_val": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "boolean",
                                                                                "number_key": "int",
                                                                                "none_key": "none",
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                        },
                                                    ],
                                                },
                                            },
                                        },
                                    ],
                                },
                            },
                        },
                        "string",
                        "boolean",
                        "int",
                        "none",
                        {
                            "type": "list",
                            "objectType": {
                                "type": "union",
                                "members": [
                                    {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": {
                                                "type": "union",
                                                "members": ["string", "none"],
                                            },
                                            "bool_key": {
                                                "type": "union",
                                                "members": ["boolean", "none"],
                                            },
                                            "number_key": {
                                                "type": "union",
                                                "members": ["int", "none"],
                                            },
                                            "none_key": "none",
                                            "custom_1": {
                                                "type": "union",
                                                "members": [
                                                    {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "_type": "string",
                                                            "_weave_type": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "type": "string",
                                                                    "propertyTypes": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "a": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "type": "string",
                                                                                    "propertyTypes": {
                                                                                        "type": "typedDict",
                                                                                        "propertyTypes": {
                                                                                            "string_key": "string",
                                                                                            "bool_key": "string",
                                                                                            "number_key": "string",
                                                                                            "none_key": "string",
                                                                                        },
                                                                                    },
                                                                                },
                                                                            }
                                                                        },
                                                                    },
                                                                },
                                                            },
                                                            "_val": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "string_key": "string",
                                                                    "bool_key": "boolean",
                                                                    "number_key": "int",
                                                                    "none_key": "none",
                                                                },
                                                            },
                                                        },
                                                    },
                                                    "none",
                                                ],
                                            },
                                            "_type": {
                                                "type": "union",
                                                "members": ["none", "string"],
                                            },
                                            "_weave_type": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "type": "string",
                                                            "propertyTypes": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "a": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "type": "string",
                                                                            "propertyTypes": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "string_key": "string",
                                                                                    "bool_key": "string",
                                                                                    "number_key": "string",
                                                                                    "none_key": "string",
                                                                                },
                                                                            },
                                                                        },
                                                                    }
                                                                },
                                                            },
                                                        },
                                                    },
                                                ],
                                            },
                                            "_val": {
                                                "type": "union",
                                                "members": [
                                                    "none",
                                                    {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "string_key": "string",
                                                            "bool_key": "boolean",
                                                            "number_key": "int",
                                                            "none_key": "none",
                                                        },
                                                    },
                                                ],
                                            },
                                        },
                                    },
                                    "string",
                                    "boolean",
                                    "int",
                                    "none",
                                ],
                            },
                        },
                    ],
                },
            },
            "dict_data_4": {
                "type": "typedDict",
                "propertyTypes": {
                    "string_key": "string",
                    "bool_key": "boolean",
                    "number_key": "int",
                    "none_key": "none",
                    "custom_1": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "_type": "string",
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "type": "string",
                                    "propertyTypes": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "type": "string",
                                                    "propertyTypes": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "string_key": "string",
                                                            "bool_key": "string",
                                                            "number_key": "string",
                                                            "none_key": "string",
                                                        },
                                                    },
                                                },
                                            }
                                        },
                                    },
                                },
                            },
                            "_val": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            },
                        },
                    },
                    "list_data_uniform_2": {
                        "type": "list",
                        "objectType": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                                "custom_1": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "_type": "string",
                                        "_weave_type": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "type": "string",
                                                "propertyTypes": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "a": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "string_key": "string",
                                                                        "bool_key": "string",
                                                                        "number_key": "string",
                                                                        "none_key": "string",
                                                                    },
                                                                },
                                                            },
                                                        }
                                                    },
                                                },
                                            },
                                        },
                                        "_val": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "list_data_mixed_2": {
                        "type": "list",
                        "objectType": {
                            "type": "union",
                            "members": [
                                {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "bool_key": {
                                            "type": "union",
                                            "members": ["boolean", "none"],
                                        },
                                        "number_key": {
                                            "type": "union",
                                            "members": ["int", "none"],
                                        },
                                        "none_key": "none",
                                        "custom_1": {
                                            "type": "union",
                                            "members": [
                                                {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "_type": "string",
                                                        "_weave_type": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "a": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "type": "string",
                                                                                "propertyTypes": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "string_key": "string",
                                                                                        "bool_key": "string",
                                                                                        "number_key": "string",
                                                                                        "none_key": "string",
                                                                                    },
                                                                                },
                                                                            },
                                                                        }
                                                                    },
                                                                },
                                                            },
                                                        },
                                                        "_val": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "boolean",
                                                                "number_key": "int",
                                                                "none_key": "none",
                                                            },
                                                        },
                                                    },
                                                },
                                                "none",
                                            ],
                                        },
                                        "string_key": {
                                            "type": "union",
                                            "members": ["none", "string"],
                                        },
                                        "_type": {
                                            "type": "union",
                                            "members": ["none", "string"],
                                        },
                                        "_weave_type": {
                                            "type": "union",
                                            "members": [
                                                "none",
                                                {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "type": "string",
                                                        "propertyTypes": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "a": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "string",
                                                                                "number_key": "string",
                                                                                "none_key": "string",
                                                                            },
                                                                        },
                                                                    },
                                                                }
                                                            },
                                                        },
                                                    },
                                                },
                                            ],
                                        },
                                        "_val": {
                                            "type": "union",
                                            "members": [
                                                "none",
                                                {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "string_key": "string",
                                                        "bool_key": "boolean",
                                                        "number_key": "int",
                                                        "none_key": "none",
                                                    },
                                                },
                                            ],
                                        },
                                    },
                                },
                                "string",
                                "boolean",
                                "int",
                                "none",
                            ],
                        },
                    },
                    "dict_data_2": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                            "custom_1": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "_type": "string",
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "type": "string",
                                            "propertyTypes": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "a": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "type": "string",
                                                            "propertyTypes": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "string_key": "string",
                                                                    "bool_key": "string",
                                                                    "number_key": "string",
                                                                    "none_key": "string",
                                                                },
                                                            },
                                                        },
                                                    }
                                                },
                                            },
                                        },
                                    },
                                    "_val": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "custom_3": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "_type": "string",
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "type": "string",
                                    "propertyTypes": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "type": "string",
                                                    "propertyTypes": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "string_key": "string",
                                                            "bool_key": "string",
                                                            "number_key": "string",
                                                            "none_key": "string",
                                                        },
                                                    },
                                                },
                                            }
                                        },
                                    },
                                },
                            },
                            "_val": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                    "custom_1": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "_type": "string",
                                            "_weave_type": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "type": "string",
                                                    "propertyTypes": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "a": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "type": "string",
                                                                    "propertyTypes": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "string_key": "string",
                                                                            "bool_key": "string",
                                                                            "number_key": "string",
                                                                            "none_key": "string",
                                                                        },
                                                                    },
                                                                },
                                                            }
                                                        },
                                                    },
                                                },
                                            },
                                            "_val": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            },
                                        },
                                    },
                                    "list_data_uniform_2": {
                                        "type": "list",
                                        "objectType": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                                "custom_1": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "_type": "string",
                                                        "_weave_type": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "type": "string",
                                                                "propertyTypes": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "a": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "type": "string",
                                                                                "propertyTypes": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "string_key": "string",
                                                                                        "bool_key": "string",
                                                                                        "number_key": "string",
                                                                                        "none_key": "string",
                                                                                    },
                                                                                },
                                                                            },
                                                                        }
                                                                    },
                                                                },
                                                            },
                                                        },
                                                        "_val": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "string_key": "string",
                                                                "bool_key": "boolean",
                                                                "number_key": "int",
                                                                "none_key": "none",
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                    "list_data_mixed_2": {
                                        "type": "list",
                                        "objectType": {
                                            "type": "union",
                                            "members": [
                                                {
                                                    "type": "typedDict",
                                                    "propertyTypes": {
                                                        "bool_key": {
                                                            "type": "union",
                                                            "members": [
                                                                "boolean",
                                                                "none",
                                                            ],
                                                        },
                                                        "number_key": {
                                                            "type": "union",
                                                            "members": ["int", "none"],
                                                        },
                                                        "none_key": "none",
                                                        "custom_1": {
                                                            "type": "union",
                                                            "members": [
                                                                {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "_type": "string",
                                                                        "_weave_type": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "type": "string",
                                                                                "propertyTypes": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "a": {
                                                                                            "type": "typedDict",
                                                                                            "propertyTypes": {
                                                                                                "type": "string",
                                                                                                "propertyTypes": {
                                                                                                    "type": "typedDict",
                                                                                                    "propertyTypes": {
                                                                                                        "string_key": "string",
                                                                                                        "bool_key": "string",
                                                                                                        "number_key": "string",
                                                                                                        "none_key": "string",
                                                                                                    },
                                                                                                },
                                                                                            },
                                                                                        }
                                                                                    },
                                                                                },
                                                                            },
                                                                        },
                                                                        "_val": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "string_key": "string",
                                                                                "bool_key": "boolean",
                                                                                "number_key": "int",
                                                                                "none_key": "none",
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                                "none",
                                                            ],
                                                        },
                                                        "string_key": {
                                                            "type": "union",
                                                            "members": [
                                                                "none",
                                                                "string",
                                                            ],
                                                        },
                                                        "_type": {
                                                            "type": "union",
                                                            "members": [
                                                                "none",
                                                                "string",
                                                            ],
                                                        },
                                                        "_weave_type": {
                                                            "type": "union",
                                                            "members": [
                                                                "none",
                                                                {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "type": "string",
                                                                        "propertyTypes": {
                                                                            "type": "typedDict",
                                                                            "propertyTypes": {
                                                                                "a": {
                                                                                    "type": "typedDict",
                                                                                    "propertyTypes": {
                                                                                        "type": "string",
                                                                                        "propertyTypes": {
                                                                                            "type": "typedDict",
                                                                                            "propertyTypes": {
                                                                                                "string_key": "string",
                                                                                                "bool_key": "string",
                                                                                                "number_key": "string",
                                                                                                "none_key": "string",
                                                                                            },
                                                                                        },
                                                                                    },
                                                                                }
                                                                            },
                                                                        },
                                                                    },
                                                                },
                                                            ],
                                                        },
                                                        "_val": {
                                                            "type": "union",
                                                            "members": [
                                                                "none",
                                                                {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "string_key": "string",
                                                                        "bool_key": "boolean",
                                                                        "number_key": "int",
                                                                        "none_key": "none",
                                                                    },
                                                                },
                                                            ],
                                                        },
                                                    },
                                                },
                                                "string",
                                                "boolean",
                                                "int",
                                                "none",
                                            ],
                                        },
                                    },
                                    "dict_data_2": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                            "custom_1": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "_type": "string",
                                                    "_weave_type": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "type": "string",
                                                            "propertyTypes": {
                                                                "type": "typedDict",
                                                                "propertyTypes": {
                                                                    "a": {
                                                                        "type": "typedDict",
                                                                        "propertyTypes": {
                                                                            "type": "string",
                                                                            "propertyTypes": {
                                                                                "type": "typedDict",
                                                                                "propertyTypes": {
                                                                                    "string_key": "string",
                                                                                    "bool_key": "string",
                                                                                    "number_key": "string",
                                                                                    "none_key": "string",
                                                                                },
                                                                            },
                                                                        },
                                                                    }
                                                                },
                                                            },
                                                        },
                                                    },
                                                    "_val": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "string_key": "string",
                                                            "bool_key": "boolean",
                                                            "number_key": "int",
                                                            "none_key": "none",
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}
