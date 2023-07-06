"""
Generated from 
def quick_weave_obj(obj):
    t = TypeRegistry.type_of({"a": {
        "string_key": "hi",
        "bool_key": True,
        "number_key": 42,
        "none_key": None}}).to_dict()
    return {
        "_type": "_wt_::" + json.dumps(t),
        "_weave_type": t,
        "_val": obj
    }
    
def add_custom_data(key, data):
    return {
        **data,
        "custom_" + key: quick_weave_obj(data),
    }

def add_container_data(key, data):
    return {
        **data,
        "list_data_uniform_" + key: [data],
        "list_data_mixed_" + key: [{k:v for k,v in data.items() if k != key} for key in data.keys()] + list(data.values()),
        "dict_data_" + key: data,
    }

def make_row():
    data = {
        "string_key": "hi",
        "bool_key": True,
        "number_key": 42,
        "none_key": None,
    }
    
    data = add_custom_data('1', data)
    data = add_container_data('2', data)
    data = add_custom_data('3', data)
    data = add_container_data('4', data)
    return data
    
"""

logs = [
    {
        "string_key": "hi",
        "bool_key": True,
        "number_key": 42,
        "none_key": None,
        "custom_1": {
            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
            "_weave_type": {
                "type": "typedDict",
                "propertyTypes": {
                    "a": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                        },
                    }
                },
            },
            "_val": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
            },
        },
        "list_data_uniform_2": [
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            }
        ],
        "list_data_mixed_2": [
            {
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {"string_key": "hi", "bool_key": True, "number_key": 42, "none_key": None},
            "hi",
            True,
            42,
            None,
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
        ],
        "dict_data_2": {
            "string_key": "hi",
            "bool_key": True,
            "number_key": 42,
            "none_key": None,
            "custom_1": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
        },
        "custom_3": {
            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
            "_weave_type": {
                "type": "typedDict",
                "propertyTypes": {
                    "a": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                        },
                    }
                },
            },
            "_val": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
            },
        },
        "list_data_uniform_4": [
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            }
        ],
        "list_data_mixed_4": [
            {
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
            },
            "hi",
            True,
            42,
            None,
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
            [
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                }
            ],
            [
                {
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
                "hi",
                True,
                42,
                None,
                {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            ],
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                    "list_data_uniform_2": [
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        }
                    ],
                    "list_data_mixed_2": [
                        {
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                        "hi",
                        True,
                        42,
                        None,
                        {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    ],
                    "dict_data_2": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                },
            },
        ],
        "dict_data_4": {
            "string_key": "hi",
            "bool_key": True,
            "number_key": 42,
            "none_key": None,
            "custom_1": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
            "list_data_uniform_2": [
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                }
            ],
            "list_data_mixed_2": [
                {
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
                "hi",
                True,
                42,
                None,
                {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            ],
            "dict_data_2": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            "custom_3": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                    "list_data_uniform_2": [
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        }
                    ],
                    "list_data_mixed_2": [
                        {
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                        "hi",
                        True,
                        42,
                        None,
                        {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    ],
                    "dict_data_2": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                },
            },
        },
    },
    {
        "string_key": "hi",
        "bool_key": True,
        "number_key": 42,
        "none_key": None,
        "custom_1": {
            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
            "_weave_type": {
                "type": "typedDict",
                "propertyTypes": {
                    "a": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                        },
                    }
                },
            },
            "_val": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
            },
        },
        "list_data_uniform_2": [
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            }
        ],
        "list_data_mixed_2": [
            {
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {"string_key": "hi", "bool_key": True, "number_key": 42, "none_key": None},
            "hi",
            True,
            42,
            None,
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
        ],
        "dict_data_2": {
            "string_key": "hi",
            "bool_key": True,
            "number_key": 42,
            "none_key": None,
            "custom_1": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
        },
        "custom_3": {
            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
            "_weave_type": {
                "type": "typedDict",
                "propertyTypes": {
                    "a": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                        },
                    }
                },
            },
            "_val": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
            },
        },
        "list_data_uniform_4": [
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            }
        ],
        "list_data_mixed_4": [
            {
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
            },
            "hi",
            True,
            42,
            None,
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
            [
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                }
            ],
            [
                {
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
                "hi",
                True,
                42,
                None,
                {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            ],
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                    "list_data_uniform_2": [
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        }
                    ],
                    "list_data_mixed_2": [
                        {
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                        "hi",
                        True,
                        42,
                        None,
                        {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    ],
                    "dict_data_2": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                },
            },
        ],
        "dict_data_4": {
            "string_key": "hi",
            "bool_key": True,
            "number_key": 42,
            "none_key": None,
            "custom_1": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
            "list_data_uniform_2": [
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                }
            ],
            "list_data_mixed_2": [
                {
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
                "hi",
                True,
                42,
                None,
                {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            ],
            "dict_data_2": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            "custom_3": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                    "list_data_uniform_2": [
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        }
                    ],
                    "list_data_mixed_2": [
                        {
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                        "hi",
                        True,
                        42,
                        None,
                        {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    ],
                    "dict_data_2": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                },
            },
        },
    },
    {
        "string_key": "hi",
        "bool_key": True,
        "number_key": 42,
        "none_key": None,
        "custom_1": {
            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
            "_weave_type": {
                "type": "typedDict",
                "propertyTypes": {
                    "a": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                        },
                    }
                },
            },
            "_val": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
            },
        },
        "list_data_uniform_2": [
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            }
        ],
        "list_data_mixed_2": [
            {
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {"string_key": "hi", "bool_key": True, "number_key": 42, "none_key": None},
            "hi",
            True,
            42,
            None,
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
        ],
        "dict_data_2": {
            "string_key": "hi",
            "bool_key": True,
            "number_key": 42,
            "none_key": None,
            "custom_1": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
        },
        "custom_3": {
            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
            "_weave_type": {
                "type": "typedDict",
                "propertyTypes": {
                    "a": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "string_key": "string",
                            "bool_key": "boolean",
                            "number_key": "int",
                            "none_key": "none",
                        },
                    }
                },
            },
            "_val": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
            },
        },
        "list_data_uniform_4": [
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            }
        ],
        "list_data_mixed_4": [
            {
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "custom_3": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                        "list_data_uniform_2": [
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            }
                        ],
                        "list_data_mixed_2": [
                            {
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "number_key": 42,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "none_key": None,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "custom_1": {
                                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                    "_weave_type": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "a": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "string_key": "string",
                                                    "bool_key": "boolean",
                                                    "number_key": "int",
                                                    "none_key": "none",
                                                },
                                            }
                                        },
                                    },
                                    "_val": {
                                        "string_key": "hi",
                                        "bool_key": True,
                                        "number_key": 42,
                                        "none_key": None,
                                    },
                                },
                            },
                            {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                            "hi",
                            True,
                            42,
                            None,
                            {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        ],
                        "dict_data_2": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                    },
                },
            },
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
                "list_data_uniform_2": [
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    }
                ],
                "list_data_mixed_2": [
                    {
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                    {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                    "hi",
                    True,
                    42,
                    None,
                    {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                ],
                "dict_data_2": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
            },
            "hi",
            True,
            42,
            None,
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
            [
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                }
            ],
            [
                {
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
                "hi",
                True,
                42,
                None,
                {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            ],
            {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                    "list_data_uniform_2": [
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        }
                    ],
                    "list_data_mixed_2": [
                        {
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                        "hi",
                        True,
                        42,
                        None,
                        {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    ],
                    "dict_data_2": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                },
            },
        ],
        "dict_data_4": {
            "string_key": "hi",
            "bool_key": True,
            "number_key": 42,
            "none_key": None,
            "custom_1": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
            },
            "list_data_uniform_2": [
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                }
            ],
            "list_data_mixed_2": [
                {
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                },
                {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                },
                "hi",
                True,
                42,
                None,
                {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            ],
            "dict_data_2": {
                "string_key": "hi",
                "bool_key": True,
                "number_key": 42,
                "none_key": None,
                "custom_1": {
                    "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                    "_weave_type": {
                        "type": "typedDict",
                        "propertyTypes": {
                            "a": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "string_key": "string",
                                    "bool_key": "boolean",
                                    "number_key": "int",
                                    "none_key": "none",
                                },
                            }
                        },
                    },
                    "_val": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                    },
                },
            },
            "custom_3": {
                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                "_weave_type": {
                    "type": "typedDict",
                    "propertyTypes": {
                        "a": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "string_key": "string",
                                "bool_key": "boolean",
                                "number_key": "int",
                                "none_key": "none",
                            },
                        }
                    },
                },
                "_val": {
                    "string_key": "hi",
                    "bool_key": True,
                    "number_key": 42,
                    "none_key": None,
                    "custom_1": {
                        "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                        "_weave_type": {
                            "type": "typedDict",
                            "propertyTypes": {
                                "a": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "string_key": "string",
                                        "bool_key": "boolean",
                                        "number_key": "int",
                                        "none_key": "none",
                                    },
                                }
                            },
                        },
                        "_val": {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                    },
                    "list_data_uniform_2": [
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        }
                    ],
                    "list_data_mixed_2": [
                        {
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "number_key": 42,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "none_key": None,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "custom_1": {
                                "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                                "_weave_type": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "a": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "string_key": "string",
                                                "bool_key": "boolean",
                                                "number_key": "int",
                                                "none_key": "none",
                                            },
                                        }
                                    },
                                },
                                "_val": {
                                    "string_key": "hi",
                                    "bool_key": True,
                                    "number_key": 42,
                                    "none_key": None,
                                },
                            },
                        },
                        {
                            "string_key": "hi",
                            "bool_key": True,
                            "number_key": 42,
                            "none_key": None,
                        },
                        "hi",
                        True,
                        42,
                        None,
                        {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    ],
                    "dict_data_2": {
                        "string_key": "hi",
                        "bool_key": True,
                        "number_key": 42,
                        "none_key": None,
                        "custom_1": {
                            "_type": '_wt_::{"type": "typedDict", "propertyTypes": {"a": {"type": "typedDict", "propertyTypes": {"string_key": "string", "bool_key": "boolean", "number_key": "int", "none_key": "none"}}}}',
                            "_weave_type": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "a": {
                                        "type": "typedDict",
                                        "propertyTypes": {
                                            "string_key": "string",
                                            "bool_key": "boolean",
                                            "number_key": "int",
                                            "none_key": "none",
                                        },
                                    }
                                },
                            },
                            "_val": {
                                "string_key": "hi",
                                "bool_key": True,
                                "number_key": 42,
                                "none_key": None,
                            },
                        },
                    },
                },
            },
        },
    },
]
