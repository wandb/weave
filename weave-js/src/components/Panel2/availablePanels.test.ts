import {list, Type} from '../../core';
import * as AvailablePanels from './availablePanels';
import {Spec as ArraySpec} from './PanelRow';

describe('availablePanels', () => {
  it('type image[]', () => {
    expect(
      AvailablePanels.getPanelStacksForType(
        list({type: 'image-file'}),
        undefined
      ).stackIds.map(sid => sid.id)
    ).toEqual(['row.image-file', 'table', 'plot']);
  });
  it('type number[]', () => {
    expect(
      AvailablePanels.getPanelStacksForType(
        list('number'),
        undefined
      ).stackIds.map(sid => sid.id)
    ).toEqual([
      'histogram',
      'row.number',
      'row.string',
      'row.Color',
      'table',
      'plot',
    ]);
  });
});

describe('panel chaining', () => {
  it('image case with lots of tags', () => {
    const type = {
      type: 'tagged',
      tag: {
        type: 'typedDict',
        propertyTypes: {
          groupKey: {
            type: 'typedDict',
            propertyTypes: {
              'dominant_pred_test[0]': {
                type: 'tagged',
                tag: {
                  type: 'tagged',
                  tag: {
                    type: 'tagged',
                    tag: {
                      type: 'tagged',
                      tag: {
                        type: 'tagged',
                        tag: {
                          type: 'typedDict',
                          propertyTypes: {
                            joinKey: 'string',
                            joinObj: {
                              type: 'tagged',
                              tag: {
                                type: 'tagged',
                                tag: {
                                  type: 'tagged',
                                  tag: {
                                    type: 'tagged',
                                    tag: {
                                      type: 'typedDict',
                                      propertyTypes: {
                                        entityName: 'string',
                                        projectName: 'string',
                                      },
                                    },
                                    value: {
                                      type: 'typedDict',
                                      propertyTypes: {
                                        project: 'project',
                                        artifactName: 'string',
                                        artifactVersionAlias: 'string',
                                      },
                                    },
                                  },
                                  value: {
                                    type: 'typedDict',
                                    propertyTypes: {
                                      file: {
                                        type: 'file',
                                        extension: 'json',
                                        wbObjectType: {
                                          type: 'table',
                                          columnTypes: {},
                                        },
                                      },
                                    },
                                  },
                                },
                                value: {
                                  type: 'typedDict',
                                  propertyTypes: {
                                    table: {
                                      type: 'union',
                                      members: [
                                        'none',
                                        {type: 'table', columnTypes: {}},
                                      ],
                                    },
                                  },
                                },
                              },
                              value: 'id',
                            },
                          },
                        },
                        value: {
                          type: 'typedDict',
                          propertyTypes: {
                            entityName: 'string',
                            projectName: 'string',
                          },
                        },
                      },
                      value: {
                        type: 'typedDict',
                        propertyTypes: {
                          project: 'project',
                          artifactName: 'string',
                          artifactVersionAlias: 'string',
                        },
                      },
                    },
                    value: {
                      type: 'typedDict',
                      propertyTypes: {
                        file: {
                          type: 'file',
                          extension: 'json',
                          wbObjectType: {type: 'table', columnTypes: {}},
                        },
                      },
                    },
                  },
                  value: {
                    type: 'typedDict',
                    propertyTypes: {
                      table: {
                        type: 'union',
                        members: ['none', {type: 'table', columnTypes: {}}],
                      },
                    },
                  },
                },
                value: 'string',
              },
            },
          },
        },
      },
      value: {
        type: 'list',
        objectType: {
          type: 'tagged',
          tag: {
            type: 'tagged',
            tag: {
              type: 'tagged',
              tag: {
                type: 'tagged',
                tag: {
                  type: 'tagged',
                  tag: {
                    type: 'typedDict',
                    propertyTypes: {
                      joinKey: 'string',
                      joinObj: {
                        type: 'tagged',
                        tag: {
                          type: 'tagged',
                          tag: {
                            type: 'tagged',
                            tag: {
                              type: 'tagged',
                              tag: {
                                type: 'typedDict',
                                propertyTypes: {
                                  entityName: 'string',
                                  projectName: 'string',
                                },
                              },
                              value: {
                                type: 'typedDict',
                                propertyTypes: {
                                  project: 'project',
                                  artifactName: 'string',
                                  artifactVersionAlias: 'string',
                                },
                              },
                            },
                            value: {
                              type: 'typedDict',
                              propertyTypes: {
                                file: {
                                  type: 'file',
                                  extension: 'json',
                                  wbObjectType: {
                                    type: 'table',
                                    columnTypes: {},
                                  },
                                },
                              },
                            },
                          },
                          value: {
                            type: 'typedDict',
                            propertyTypes: {
                              table: {
                                type: 'union',
                                members: [
                                  'none',
                                  {type: 'table', columnTypes: {}},
                                ],
                              },
                            },
                          },
                        },
                        value: 'id',
                      },
                    },
                  },
                  value: {
                    type: 'typedDict',
                    propertyTypes: {
                      entityName: 'string',
                      projectName: 'string',
                    },
                  },
                },
                value: {
                  type: 'typedDict',
                  propertyTypes: {
                    project: 'project',
                    artifactName: 'string',
                    artifactVersionAlias: 'string',
                  },
                },
              },
              value: {
                type: 'typedDict',
                propertyTypes: {
                  file: {
                    type: 'file',
                    extension: 'json',
                    wbObjectType: {type: 'table', columnTypes: {}},
                  },
                },
              },
            },
            value: {
              type: 'typedDict',
              propertyTypes: {
                table: {
                  type: 'union',
                  members: ['none', {type: 'table', columnTypes: {}}],
                },
              },
            },
          },
          value: {type: 'list', objectType: {type: 'image-file'}, maxLength: 2},
        },
      },
    } as Type;
    const many1 = ArraySpec.convert(type);
    expect(many1).not.toBeNull();
    if (many1 == null) {
      throw new Error('invalid');
    }
    const many2 = ArraySpec.convert(many1);
    expect(many2).not.toBeNull();
    expect(many2).toEqual({type: 'image-file'});
    expect(
      AvailablePanels.getPanelStacksForType(type, undefined).stackIds.map(
        sid => sid.id
      )
    ).toContain('row.row.image-file');
  });

  it('maybe file case', () => {
    const type = {
      type: 'tagged',
      tag: {
        type: 'tagged',
        tag: {
          type: 'tagged',
          tag: {
            type: 'tagged',
            tag: {
              type: 'tagged',
              tag: {
                type: 'typedDict',
                propertyTypes: {
                  entityName: 'string',
                  projectName: 'string',
                },
              },
              value: {
                type: 'typedDict',
                propertyTypes: {
                  project: 'project',
                  filter: 'string',
                  order: 'string',
                },
              },
            },
            value: {
              type: 'typedDict',
              propertyTypes: {
                entityName: 'string',
                projectName: 'string',
              },
            },
          },
          value: {
            type: 'typedDict',
            propertyTypes: {
              project: 'project',
              filter: 'string',
              order: 'string',
            },
          },
        },
        value: {
          type: 'typedDict',
          propertyTypes: {
            run: 'run',
          },
        },
      },
      value: {
        type: 'union',
        members: [
          'none',
          {
            type: 'file',
            _base_type: {
              type: 'FileBase',
            },
            extension: 'json',
            wbObjectType: {
              type: 'table',
              _base_type: {
                type: 'Object',
              },
              _is_object: true,
              _rows: {
                type: 'ArrowWeaveList',
                _base_type: {
                  type: 'list',
                },
                objectType: {
                  type: 'typedDict',
                  propertyTypes: {},
                },
              },
            },
          },
        ],
      },
    } as Type;

    const stacks = AvailablePanels.getPanelStacksForType(type, undefined, {
      excludeTable: true,
      excludeMultiTable: true,
      excludePlot: true,
    }).stackIds.map(s => s.id);

    expect(stacks).toEqual(['maybe.object-file.object']);
  });
});
