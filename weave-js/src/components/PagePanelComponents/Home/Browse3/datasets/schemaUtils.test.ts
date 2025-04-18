import {
  CallData,
  createProcessedRowsMap,
  createSourceSchema,
  createTargetSchema,
  extractTopLevelFields,
  inferType,
  mapCallsToDatasetRows,
  unwrapRefValue,
} from './schemaUtils';

describe('inferType', () => {
  test('identifies null type', () => {
    expect(inferType(null)).toBe('null');
  });

  test('identifies array type', () => {
    expect(inferType([])).toBe('array');
    expect(inferType([1, 2, 3])).toBe('array');
  });

  test('identifies date type', () => {
    expect(inferType(new Date())).toBe('date');
  });

  test('identifies object type', () => {
    expect(inferType({})).toBe('object');
    expect(inferType({key: 'value'})).toBe('object');
  });

  test('identifies primitive types', () => {
    expect(inferType('string')).toBe('string');
    expect(inferType(42)).toBe('number');
    expect(inferType(true)).toBe('boolean');
    expect(inferType(undefined)).toBe('undefined');
  });
});

describe('extractTopLevelFields', () => {
  test('extracts only top-level fields', () => {
    const obj = {
      user: {
        name: 'Alice',
        address: {
          city: 'Paris',
        },
      },
      age: 30,
    };

    expect(extractTopLevelFields(obj)).toEqual([
      {name: 'user', type: 'object'},
      {name: 'age', type: 'number'},
    ]);
  });

  test('handles arrays as single fields', () => {
    const obj = {tags: ['a', 'b', 'c']};
    expect(extractTopLevelFields(obj)).toEqual([{name: 'tags', type: 'array'}]);
  });

  test('handles prefix correctly', () => {
    const obj = {name: 'Alice', age: 30};
    expect(extractTopLevelFields(obj, 'user')).toEqual([
      {name: 'user.name', type: 'string'},
      {name: 'user.age', type: 'number'},
    ]);
  });
});

describe('createTargetSchema', () => {
  test('creates schema from single object', () => {
    const data = {name: 'Alice', age: 30};
    expect(createTargetSchema(data)).toEqual([
      {name: 'name', type: 'string'},
      {name: 'age', type: 'number'},
    ]);
  });

  test('handles arrays as single fields with array type', () => {
    const data = {
      name: 'Alice',
      tags: ['tag1', 'tag2'],
      scores: [90, 85, 95],
    };

    expect(createTargetSchema(data)).toEqual([
      {name: 'name', type: 'string'},
      {name: 'tags', type: 'array'},
      {name: 'scores', type: 'array'},
    ]);
  });

  test('does not flatten nested objects in target schema', () => {
    const data = {
      user: {
        name: 'Alice',
        profile: {
          age: 30,
          hobbies: ['reading', 'coding'],
        },
      },
    };

    expect(createTargetSchema(data)).toEqual([{name: 'user', type: 'object'}]);
  });

  test('handles empty input', () => {
    expect(createTargetSchema([])).toEqual([]);
    expect(createTargetSchema({})).toEqual([]);
  });

  test('handles mixed types including null/undefined', () => {
    const data = {
      value1: 42,
      value2: null,
      value3: 'text',
      value4: undefined,
    };

    expect(createTargetSchema(data)).toEqual([
      {name: 'value1', type: 'number'},
      {name: 'value2', type: 'null'},
      {name: 'value3', type: 'string'},
      {name: 'value4', type: 'undefined'},
    ]);
  });

  test('processes arrays of objects (dataset rows)', () => {
    const data = [
      {id: 1, name: 'Alice', tags: ['tag1', 'tag2']},
      {id: 2, name: 'Bob', details: {age: 30}},
      {id: 3, name: 'Charlie', scores: [90, 95, 100]},
    ];

    expect(createTargetSchema(data)).toEqual([
      {name: 'id', type: 'number'},
      {name: 'name', type: 'string'},
      {name: 'tags', type: 'array'},
      {name: 'details', type: 'object'},
      {name: 'scores', type: 'array'},
    ]);
  });
});

describe('createSourceSchema', () => {
  const mockTraceCallProps = {
    project_id: 'test-project',
    id: 'test-id',
    op_name: 'test-op',
    trace_id: 'test-trace',
    span_id: 'test-span',
    timestamp: 123456789,
    started_at: '123456789',
    attributes: {},
  };

  test('creates schema from call data with top-level fields only', () => {
    const calls: CallData[] = [
      {
        digest: '123',
        val: {
          ...mockTraceCallProps,
          inputs: {
            prompt: 'Hello',
            options: {
              temperature: 0.7,
              details: {
                mode: 'creative',
              },
            },
          },
          output: 'Hi there!',
        },
      },
    ];

    expect(createSourceSchema(calls)).toEqual([
      {name: 'inputs.prompt', type: 'string'},
      {name: 'inputs.options', type: 'object'},
      {name: 'output', type: 'string'},
    ]);
  });

  test('handles structured outputs', () => {
    const calls: CallData[] = [
      {
        digest: '123',
        val: {
          ...mockTraceCallProps,
          inputs: {prompt: 'Tell me about Paris'},
          output: {
            text: 'Paris is the capital of France',
            metadata: {
              confidence: 0.95,
              sources: ['Wikipedia'],
            },
          },
        },
      },
    ];

    expect(createSourceSchema(calls)).toEqual([
      {name: 'inputs.prompt', type: 'string'},
      {name: 'output.text', type: 'string'},
      {name: 'output.metadata', type: 'object'},
    ]);
  });

  test('filters out inputs.self and merges duplicates', () => {
    const calls: CallData[] = [
      {
        digest: '123',
        val: {
          ...mockTraceCallProps,
          inputs: {
            prompt: 'Hello',
            self: {id: '456'},
          },
          output: 'Hi',
        },
      },
      {
        digest: '456',
        val: {
          ...mockTraceCallProps,
          inputs: {
            prompt: 'Goodbye',
          },
          output: 'Bye',
        },
      },
    ];

    expect(createSourceSchema(calls)).toEqual([
      {name: 'inputs.prompt', type: 'string'},
      {name: 'output', type: 'string'},
    ]);
  });
});

describe('mapCallsToDatasetRows', () => {
  const mockTraceCallProps = {
    project_id: 'test-project',
    id: 'test-id',
    op_name: 'test-op',
    trace_id: 'test-trace',
    span_id: 'test-span',
    timestamp: 123456789,
    started_at: '123456789',
    attributes: {},
  };

  test('maps calls to rows with primitive values', () => {
    const calls: CallData[] = [
      {
        digest: 'call1',
        val: {
          ...mockTraceCallProps,
          inputs: {
            prompt: 'Hello world',
            temperature: 0.7,
          },
          output: 'Response text',
        },
      },
    ];

    const fieldMappings = [
      {sourceField: 'inputs.prompt', targetField: 'prompt'},
      {sourceField: 'inputs.temperature', targetField: 'temp'},
      {sourceField: 'output', targetField: 'response'},
    ];

    const result = mapCallsToDatasetRows(calls, fieldMappings);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      ___weave: {
        id: 'call1',
        isNew: true,
      },
      prompt: 'Hello world',
      temp: 0.7,
      response: 'Response text',
    });
  });

  test('flattens nested objects in the output', () => {
    const calls: CallData[] = [
      {
        digest: 'call2',
        val: {
          ...mockTraceCallProps,
          inputs: {
            user: {
              name: 'Alice',
              profile: {
                age: 30,
                location: 'New York',
              },
            },
          },
          output: 'OK',
        },
      },
    ];

    const fieldMappings = [
      {sourceField: 'inputs.user', targetField: 'user_data'},
    ];

    const result = mapCallsToDatasetRows(calls, fieldMappings);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      ___weave: {
        id: 'call2',
        isNew: true,
      },
      'user_data.name': 'Alice',
      'user_data.profile.age': 30,
      'user_data.profile.location': 'New York',
    });
  });

  test('preserves arrays without flattening them', () => {
    const calls: CallData[] = [
      {
        digest: 'call3',
        val: {
          ...mockTraceCallProps,
          inputs: {
            tags: ['tag1', 'tag2', 'tag3'],
            config: {
              options: ['opt1', 'opt2'],
              nested: {
                array: [1, 2, 3],
              },
            },
          },
          output: 'OK',
        },
      },
    ];

    const fieldMappings = [
      {sourceField: 'inputs.tags', targetField: 'tags'},
      {sourceField: 'inputs.config', targetField: 'config'},
    ];

    const result = mapCallsToDatasetRows(calls, fieldMappings);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      ___weave: {
        id: 'call3',
        isNew: true,
      },
      tags: ['tag1', 'tag2', 'tag3'],
      'config.options': ['opt1', 'opt2'],
      'config.nested.array': [1, 2, 3],
    });
  });

  test('handles ref/val pattern correctly', () => {
    const calls: CallData[] = [
      {
        digest: 'call4',
        val: {
          ...mockTraceCallProps,
          inputs: {
            data: {
              __ref__: 'ref-id',
              __val__: {
                name: 'Test',
                details: {
                  __ref__: 'nested-ref',
                  __val__: {
                    score: 95,
                  },
                },
              },
            },
          },
          output: 'OK',
        },
      },
    ];

    const fieldMappings = [{sourceField: 'inputs.data', targetField: 'data'}];

    const result = mapCallsToDatasetRows(calls, fieldMappings);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      ___weave: {
        id: 'call4',
        isNew: true,
      },
      'data.name': 'Test',
      'data.details.score': 95,
    });
  });

  test('handles mixed flat and nested mappings', () => {
    const calls: CallData[] = [
      {
        digest: 'call6',
        val: {
          ...mockTraceCallProps,
          inputs: {
            simple: 'value',
            nested: {
              prop1: 'val1',
              prop2: 'val2',
            },
          },
          output: {
            result: 'success',
            metadata: {
              time: 123,
            },
          },
        },
      },
    ];

    const fieldMappings = [
      {sourceField: 'inputs.simple', targetField: 'simple'},
      {sourceField: 'inputs.nested', targetField: 'complex'},
      {sourceField: 'output', targetField: 'output'},
    ];

    const result = mapCallsToDatasetRows(calls, fieldMappings);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      ___weave: {
        id: 'call6',
        isNew: true,
      },
      simple: 'value',
      'complex.prop1': 'val1',
      'complex.prop2': 'val2',
      'output.result': 'success',
      'output.metadata.time': 123,
    });
  });
});

describe('unwrapRefValue', () => {
  test('unwraps simple ref/val pattern', () => {
    const input = {
      __ref__: 'ref-id',
      __val__: 'actual value',
    };

    expect(unwrapRefValue(input)).toBe('actual value');
  });

  test('unwraps nested ref/val patterns', () => {
    const input = {
      __ref__: 'outer-ref',
      __val__: {
        name: 'Test',
        details: {
          __ref__: 'inner-ref',
          __val__: {
            score: 95,
          },
        },
      },
    };

    expect(unwrapRefValue(input)).toEqual({
      name: 'Test',
      details: {
        score: 95,
      },
    });
  });

  test('handles arrays with ref/val objects', () => {
    const input = [
      {
        __ref__: 'ref1',
        __val__: 'value1',
      },
      {
        __ref__: 'ref2',
        __val__: 'value2',
      },
    ];

    expect(unwrapRefValue(input)).toEqual(['value1', 'value2']);
  });

  test('returns primitive values unchanged', () => {
    expect(unwrapRefValue('string')).toBe('string');
    expect(unwrapRefValue(42)).toBe(42);
    expect(unwrapRefValue(true)).toBe(true);
    expect(unwrapRefValue(null)).toBe(null);
    expect(unwrapRefValue(undefined)).toBe(undefined);
  });
});

describe('createProcessedRowsMap', () => {
  test('creates a map from row data with schema filtering', () => {
    const mappedRows = [
      {
        ___weave: {id: 'row1', isNew: true},
        name: 'Alice',
        age: 30,
        extra: 'This should be filtered out',
      },
      {
        ___weave: {id: 'row2', isNew: true},
        name: 'Bob',
        age: 25,
        score: 95,
      },
    ];

    const datasetObject = {
      schema: [
        {name: 'name', type: 'string'},
        {name: 'age', type: 'number'},
      ],
    };

    const result = createProcessedRowsMap(mappedRows, datasetObject);

    expect(result.size).toBe(2);

    // First row - extra field should be filtered out
    const row1 = result.get('row1');
    expect(row1).toHaveProperty('name', 'Alice');
    expect(row1).toHaveProperty('age', 30);
    expect(row1).not.toHaveProperty('extra');
    expect(row1.___weave.serverValue).toEqual({name: 'Alice', age: 30});

    // Second row - score field should be filtered out
    const row2 = result.get('row2');
    expect(row2).toHaveProperty('name', 'Bob');
    expect(row2).toHaveProperty('age', 25);
    expect(row2).not.toHaveProperty('score');
    expect(row2.___weave.serverValue).toEqual({name: 'Bob', age: 25});
  });
});
