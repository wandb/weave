import {defaultLanguageBinding} from '../../language';
import {
  opDateToNumber,
  opMap,
  opNumberEqual,
  opPick,
  opProjectCreatedAt,
  opProjectName,
  opProjectRuns,
  opRootProject,
  opRunName,
  opRunSummary,
} from '../../ops';
import {
  constDate,
  constFunction,
  constString,
  varNode,
  voidNode,
} from './construction';
import * as Serialization from './serialize';

describe('serialize/deserialize', () => {
  it('correctly handles simple query with var', () => {
    const graph = opRunName({
      run: varNode('run', 'x'),
    });

    const EXPECTED_PAYLOAD = {
      nodes: [
        {
          fromOp: 1,
          id: '2186614384631483',
          nodeType: 'output',
          type: {
            tag: {
              propertyTypes: {
                run: 'run',
              },
              type: 'typedDict',
            },
            type: 'tagged',
            value: 'string',
          },
        },
        {inputs: {run: 2}, name: 'run-name'},
        {nodeType: 'var', type: 'run', varName: 'x'},
      ],
      targetNodes: [0],
    };

    const serialized = Serialization.serialize([graph]);
    expect(serialized).toEqual(EXPECTED_PAYLOAD);

    const originalString = defaultLanguageBinding.printGraph(graph);
    expect(
      defaultLanguageBinding.printGraph(
        Serialization.deserialize(serialized)[0]
      )
    ).toEqual(originalString);
  });

  it('correctly handles simple query with void', () => {
    const graph = opRunName({
      run: voidNode() as any,
    });

    const EXPECTED_PAYLOAD = {
      nodes: [
        {
          fromOp: 1,
          id: '7541259424733123',
          nodeType: 'output',
          type: {
            tag: {
              propertyTypes: {
                run: 'invalid',
              },
              type: 'typedDict',
            },
            type: 'tagged',
            value: 'string',
          },
        },
        {inputs: {run: 2}, name: 'run-name'},
        {nodeType: 'void', type: 'invalid'},
      ],
      targetNodes: [0],
    };

    const serialized = Serialization.serialize([graph]);
    expect(serialized).toEqual(EXPECTED_PAYLOAD);

    const originalString = defaultLanguageBinding.printGraph(graph);
    expect(
      defaultLanguageBinding.printGraph(
        Serialization.deserialize(serialized)[0]
      )
    ).toEqual(originalString);
  });

  it('correctly handles basic consts', () => {
    const graph = opProjectName({
      project: opRootProject({
        entityName: constString('entity'),
        projectName: constString('project'),
      }),
    });

    const EXPECTED_PAYLOAD = {
      nodes: [
        {
          fromOp: 1,
          id: '7648570681505258',
          nodeType: 'output',
          type: {
            tag: {
              tag: {
                propertyTypes: {
                  entityName: 'string',
                  projectName: 'string',
                },
                type: 'typedDict',
              },
              type: 'tagged',
              value: {
                propertyTypes: {
                  project: 'project',
                },
                type: 'typedDict',
              },
            },
            type: 'tagged',
            value: 'string',
          },
        },
        {
          inputs: {
            project: 2,
          },
          name: 'project-name',
        },
        {
          fromOp: 3,
          id: '1794291506987101',
          nodeType: 'output',
          type: {
            tag: {
              propertyTypes: {
                entityName: 'string',
                projectName: 'string',
              },
              type: 'typedDict',
            },
            type: 'tagged',
            value: 'project',
          },
        },
        {
          inputs: {
            entityName: 4,
            projectName: 5,
          },
          name: 'root-project',
        },
        {
          nodeType: 'const',
          type: 'string',
          val: 'entity',
        },
        {
          nodeType: 'const',
          type: 'string',
          val: 'project',
        },
      ],
      targetNodes: [0],
    };

    const serialized = Serialization.serialize([graph]);
    expect(serialized).toEqual(EXPECTED_PAYLOAD);

    const originalString = defaultLanguageBinding.printGraph(graph);
    expect(
      defaultLanguageBinding.printGraph(
        Serialization.deserialize(serialized)[0]
      )
    ).toEqual(originalString);
  });

  it('correctly handles complex single result', () => {
    const graph = opMap({
      arr: opProjectRuns({
        project: opRootProject({
          entityName: constString('entity'),
          projectName: constString('project'),
        }),
      }) as any,
      mapFn: constFunction({row: 'run'}, ({row}) =>
        opRunName({
          run: row,
        })
      ) as any,
    });

    const EXPECTED_PAYLOAD = {
      nodes: [
        {
          fromOp: 1,
          id: '5533619768196527',
          nodeType: 'output',
          type: {
            tag: {
              tag: {
                propertyTypes: {
                  entityName: 'string',
                  projectName: 'string',
                },
                type: 'typedDict',
              },
              type: 'tagged',
              value: {
                propertyTypes: {
                  project: 'project',
                },
                type: 'typedDict',
              },
            },
            type: 'tagged',
            value: {
              objectType: {
                tag: {
                  propertyTypes: {
                    run: 'run',
                  },
                  type: 'typedDict',
                },
                type: 'tagged',
                value: 'string',
              },
              type: 'list',
            },
          },
        },
        {inputs: {arr: 2, mapFn: 8}, name: 'map'},
        {
          fromOp: 3,
          id: '2680172916888359',
          nodeType: 'output',
          type: {
            tag: {
              tag: {
                propertyTypes: {
                  entityName: 'string',
                  projectName: 'string',
                },
                type: 'typedDict',
              },
              type: 'tagged',
              value: {
                propertyTypes: {
                  project: 'project',
                },
                type: 'typedDict',
              },
            },
            type: 'tagged',
            value: {
              objectType: 'run',
              type: 'list',
            },
          },
        },
        {inputs: {project: 4}, name: 'project-runs'},
        {
          fromOp: 5,
          id: '1794291506987101',
          nodeType: 'output',
          type: {
            tag: {
              propertyTypes: {
                entityName: 'string',
                projectName: 'string',
              },
              type: 'typedDict',
            },
            type: 'tagged',
            value: 'project',
          },
        },
        {inputs: {entityName: 6, projectName: 7}, name: 'root-project'},
        {nodeType: 'const', type: 'string', val: 'entity'},
        {nodeType: 'const', type: 'string', val: 'project'},
        {
          nodeType: 'const',
          type: {
            inputTypes: {row: 'run'},
            outputType: {
              tag: {propertyTypes: {run: 'run'}, type: 'typedDict'},
              type: 'tagged',
              value: 'string',
            },
            type: 'function',
          },
          val: {fromOp: 10, nodeType: 'output'},
        },
        {
          fromOp: 10,
          id: '1124858538075157',
          nodeType: 'output',
          type: {
            tag: {
              propertyTypes: {
                run: 'run',
              },
              type: 'typedDict',
            },
            type: 'tagged',
            value: 'string',
          },
        },
        {inputs: {run: 11}, name: 'run-name'},
        {nodeType: 'var', type: 'run', varName: 'row'},
      ],
      targetNodes: [0],
    };
    // const EXPECTED_PAYLOAD = null;

    const serialized = Serialization.serialize([graph]);
    expect(serialized).toEqual(EXPECTED_PAYLOAD);

    const originalString = defaultLanguageBinding.printGraph(graph);
    expect(
      defaultLanguageBinding.printGraph(
        Serialization.deserialize(serialized)[0]
      )
    ).toEqual(originalString);
  });

  it('correctly handles table', () => {
    const TABLE_GRAPH = {
      nodes: [
        {
          id: '6202461649450844',
          nodeType: 'output',
          fromOp: 1,
          type: 'none',
        },
        {
          name: 'map',
          inputs: {
            arr: 2,
            mapFn: 23,
          },
        },
        {
          id: '3721883630302644',
          nodeType: 'output',
          fromOp: 3,
          type: 'none',
        },
        {
          name: 'sort',
          inputs: {
            arr: 4,
            compFn: 16,
            columnDirs: 22,
          },
        },
        {
          id: '5743108561076252',
          nodeType: 'output',
          fromOp: 5,
          type: 'none',
        },
        {
          name: 'groupby',
          inputs: {
            arr: 6,
            groupByFn: 8,
          },
        },
        {
          id: '5817233867097116',
          nodeType: 'output',
          fromOp: 7,
          type: 'none',
        },
        {
          name: 'root-featuredreports',
          inputs: {},
        },
        {
          nodeType: 'const',
          type: {
            type: 'function',
            inputTypes: {
              row: 'report',
            },
            outputType: {
              type: 'typedDict',
              propertyTypes: {
                creatorname: 'string',
              },
            },
          },
          val: {
            nodeType: 'output',
            fromOp: 10,
          },
        },
        {
          id: '6253327973006988',
          nodeType: 'output',
          fromOp: 10,
          type: {
            propertyTypes: {
              creatorname: 'none',
            },
            type: 'typedDict',
          },
        },
        {
          name: 'dict',
          inputs: {
            creatorname: 11,
          },
        },
        {
          id: '6997781524569472',
          nodeType: 'output',
          fromOp: 12,
          type: 'none',
        },
        {
          name: 'user-name',
          inputs: {
            user: 13,
          },
        },
        {
          id: '1971294485850163',
          nodeType: 'output',
          fromOp: 14,
          type: 'none',
        },
        {
          name: 'report-creator',
          inputs: {
            report: 15,
          },
        },
        {
          nodeType: 'var',
          type: 'report',
          varName: 'x',
        },
        {
          nodeType: 'const',
          type: {
            type: 'function',
            inputTypes: {
              row: {
                type: 'tagged',
                tag: {
                  type: 'typedDict',
                  propertyTypes: {
                    groupKey: {
                      type: 'typedDict',
                      propertyTypes: {
                        creatorname: 'string',
                      },
                    },
                  },
                },
                value: {
                  type: 'list',
                  objectType: 'report',
                },
              },
            },
            outputType: {
              type: 'list',
              objectType: 'number',
              minLength: 1,
              maxLength: 1,
            },
          },
          val: {
            nodeType: 'output',
            fromOp: 18,
          },
        },
        {
          id: '6801494696156248',
          nodeType: 'output',
          fromOp: 18,
          type: {
            maxLength: 1,
            minLength: 1,
            objectType: 'none',
            type: 'list',
          },
        },
        {
          name: 'list',
          inputs: {
            'col-xtmr12bzs': 19,
          },
        },
        {
          id: '2215239390794892',
          nodeType: 'output',
          fromOp: 20,
          type: 'none',
        },
        {
          name: 'count',
          inputs: {
            arr: 21,
          },
        },
        {
          nodeType: 'var',
          type: {
            type: 'list',
            objectType: 'report',
          },
          varName: 'x',
        },
        {
          nodeType: 'const',
          type: {
            type: 'list',
            objectType: 'string',
          },
          val: ['desc'],
        },
        {
          nodeType: 'const',
          type: {
            type: 'function',
            inputTypes: {
              row: {
                type: 'tagged',
                tag: {
                  type: 'typedDict',
                  propertyTypes: {
                    groupKey: {
                      type: 'typedDict',
                      propertyTypes: {
                        creatorname: 'string',
                      },
                    },
                  },
                },
                value: {
                  type: 'list',
                  objectType: 'report',
                },
              },
              index: 'number',
            },
            outputType: {
              type: 'typedDict',
              propertyTypes: {
                creatorname: 'string',
                count: 'number',
                _index: 'number',
              },
            },
          },
          val: {
            nodeType: 'output',
            fromOp: 25,
          },
        },
        {
          id: '6975314837077825',
          nodeType: 'output',
          fromOp: 25,
          type: {
            propertyTypes: {},
            type: 'typedDict',
          },
        },
        {
          name: 'merge',
          inputs: {
            lhs: 26,
            rhs: 29,
          },
        },
        {
          id: '5510634882298645',
          nodeType: 'output',
          fromOp: 27,
          type: 'none',
        },
        {
          name: 'group-groupkey',
          inputs: {
            obj: 28,
          },
        },
        {
          nodeType: 'var',
          type: {
            type: 'tagged',
            tag: {
              type: 'typedDict',
              propertyTypes: {
                groupKey: {
                  type: 'typedDict',
                  propertyTypes: {
                    creatorname: 'string',
                  },
                },
              },
            },
            value: {
              type: 'list',
              objectType: 'report',
            },
          },
          varName: 'row',
        },
        {
          id: '5561767612564503',
          nodeType: 'output',
          fromOp: 30,
          type: 'none',
        },
        {
          name: 'dict',
          inputs: {
            count: 19,
            _index: 31,
          },
        },
        {
          nodeType: 'var',
          type: 'number',
          varName: 'index',
        },
      ],
      targetNodes: [0],
    };

    const deserialized = Serialization.deserialize(TABLE_GRAPH as any);
    const serialized = Serialization.serialize(deserialized);

    expect(serialized).toEqual(TABLE_GRAPH);
  });

  it('correctly handles date', () => {
    const now = new Date(0);
    const graph = opNumberEqual({
      lhs: opDateToNumber({
        date: opProjectCreatedAt({
          project: opRootProject({
            entityName: constString('entity'),
            projectName: constString('project'),
          }),
        }),
      }),
      rhs: constDate(now),
    });

    const EXPECTED_PAYLOAD = {
      nodes: [
        {
          fromOp: 1,
          id: '8971911886648302',
          nodeType: 'output',
          type: {
            tag: {
              tag: {
                propertyTypes: {
                  entityName: 'string',
                  projectName: 'string',
                },
                type: 'typedDict',
              },
              type: 'tagged',
              value: {
                propertyTypes: {
                  project: 'project',
                },
                type: 'typedDict',
              },
            },
            type: 'tagged',
            value: 'boolean',
          },
        },
        {inputs: {lhs: 2, rhs: 10}, name: 'number-equal'},
        {
          fromOp: 3,
          id: '8973732951863413',
          nodeType: 'output',
          type: {
            tag: {
              tag: {
                propertyTypes: {
                  entityName: 'string',
                  projectName: 'string',
                },
                type: 'typedDict',
              },
              type: 'tagged',
              value: {
                propertyTypes: {
                  project: 'project',
                },
                type: 'typedDict',
              },
            },
            type: 'tagged',
            value: 'number',
          },
        },
        {inputs: {date: 4}, name: 'date-toNumber'},
        {
          fromOp: 5,
          id: '6566331007144135',
          nodeType: 'output',
          type: {
            tag: {
              tag: {
                propertyTypes: {
                  entityName: 'string',
                  projectName: 'string',
                },
                type: 'typedDict',
              },
              type: 'tagged',
              value: {
                propertyTypes: {
                  project: 'project',
                },
                type: 'typedDict',
              },
            },
            type: 'tagged',
            value: 'date',
          },
        },
        {inputs: {project: 6}, name: 'project-createdAt'},
        {
          fromOp: 7,
          id: '1794291506987101',
          nodeType: 'output',
          type: {
            tag: {
              propertyTypes: {
                entityName: 'string',
                projectName: 'string',
              },
              type: 'typedDict',
            },
            type: 'tagged',
            value: 'project',
          },
        },
        {inputs: {entityName: 8, projectName: 9}, name: 'root-project'},
        {nodeType: 'const', type: 'string', val: 'entity'},
        {nodeType: 'const', type: 'string', val: 'project'},
        {
          nodeType: 'const',
          type: 'date',
          val: {type: 'date', val: now},
        },
      ],
      targetNodes: [0],
    };

    const serialized = Serialization.serialize([graph]);
    expect(serialized).toEqual(EXPECTED_PAYLOAD);

    const originalString = defaultLanguageBinding.printGraph(graph);
    expect(
      defaultLanguageBinding.printGraph(
        Serialization.deserialize(serialized)[0]
      )
    ).toEqual(originalString);
  });

  it('correctly retains duplicate nodes in input array', () => {
    // Otherwise, we lose context of what was originally requested by caller

    const graph = opPick({
      obj: opRunSummary({run: varNode('run', 'row')}),
      key: constString('x'),
    });

    const serialized = Serialization.serialize([graph, graph, graph]);
    expect(serialized).toEqual({
      nodes: [
        {
          fromOp: 1,
          id: '7745600396373614',
          nodeType: 'output',
          type: {
            tag: {
              propertyTypes: {
                run: 'run',
              },
              type: 'typedDict',
            },
            type: 'tagged',
            value: 'none',
          },
        },
        {inputs: {key: 5, obj: 2}, name: 'pick'},
        {
          fromOp: 3,
          id: '6766779227881132',
          nodeType: 'output',
          type: {
            tag: {
              propertyTypes: {
                run: 'run',
              },
              type: 'typedDict',
            },
            type: 'tagged',
            value: {
              propertyTypes: {},
              type: 'typedDict',
            },
          },
        },
        {inputs: {run: 4}, name: 'run-summary'},
        {nodeType: 'var', type: 'run', varName: 'row'},
        {nodeType: 'const', type: 'string', val: 'x'},
      ],
      targetNodes: [0, 0, 0],
    });

    const deserialized = Serialization.deserialize(serialized);

    const originalString = defaultLanguageBinding.printGraph(graph);
    expect(defaultLanguageBinding.printGraph(deserialized[0])).toEqual(
      originalString
    );
    expect(defaultLanguageBinding.printGraph(deserialized[1])).toEqual(
      originalString
    );
    expect(defaultLanguageBinding.printGraph(deserialized[2])).toEqual(
      originalString
    );
  });
});
