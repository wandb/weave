import {DB} from './_external/backendProviders/serverApiTest';
import * as HL from './hl';
import {defaultLanguageBinding} from './language';
import {
  EditingNode,
  EditingOp,
  EditingOutputNode,
  emptyStack,
  pushFrame,
  Type,
} from './model';
import {
  constNumber,
  constString,
  list,
  maybe,
  taggedValue,
  typedDict,
  varNode,
  voidNode,
} from './model';
import {
  opGetProjectTag,
  opNumberAdd,
  opNumberEqual,
  opNumberGreaterEqual,
  opNumberLessEqual,
  opNumbersAvg,
  opProjectArtifact,
  opProjectArtifactType,
  opProjectArtifactVersion,
  opProjectRuns,
  opRootProject,
} from './ops';
import {autosuggest, AutosuggestResult} from './suggest';
import {testClient} from './testUtil';
// Do an op to force importing ops.ts, if we don't do this, ops don't
// get registered and nothing works!
opNumberAdd({lhs: constNumber(0), rhs: constNumber(1)});

function suggestResultNames(result: Array<{newNodeOrOp: EditingNode}>) {
  return result.map(r =>
    defaultLanguageBinding
      .printGraph(r.newNodeOrOp)
      .replace(/\n/g, '')
      .replace(/ /g, '')
  );
}

function expectOnlyNodes(
  result: Array<AutosuggestResult<any>>
): asserts result is Array<AutosuggestResult<EditingNode>> {
  for (const r of result) {
    expect(HL.isEditingNode(r.newNodeOrOp)).toEqual(true);
  }
}

function expectOnlyOps(
  result: Array<AutosuggestResult<any>>
): asserts result is Array<AutosuggestResult<EditingOp>> {
  for (const r of result) {
    expect(HL.isEditingOp(r.newNodeOrOp)).toEqual(true);
  }
}

describe('autosuggest project artifact types', () => {
  it('suggest project artifact types', async () => {
    const client = await testClient();
    const vNode = voidNode();

    const graph = opProjectArtifactType({
      project: opRootProject({
        entityName: constString('shawn'),
        projectName: constString('dsviz_demo'),
      }),
      artifactType: vNode,
    } as any);
    const result = await autosuggest(client, vNode, graph, []);

    expectOnlyNodes(result);
    const expectedTypes = new Set(DB.artifactTypes.map(at => `"${at.name}"`));
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toEqual(
      expect.arrayContaining(Array.from(expectedTypes))
    );
  });
  it('suggest project artifact types with tag project node', async () => {
    const client = await testClient();
    const vNode = voidNode();
    const tagProjectNode = opGetProjectTag({
      obj: varNode(
        taggedValue(
          typedDict({entityName: 'string', projectName: 'string'}),
          typedDict({
            project: 'project',
            filter: 'string',
            order: 'string',
          })
        ),
        'runs'
      ),
    });

    const graph = opProjectArtifactType({
      project: tagProjectNode,
      artifactType: vNode,
    } as any);

    const frame = {
      runs: opProjectRuns({
        project: opRootProject({
          entityName: constString('shawn'),
          projectName: constString('dsviz_demo'),
        }),
      }),
    };

    const result = await autosuggest(
      client,
      vNode,
      graph,
      pushFrame(emptyStack(), frame)
    );
    expectOnlyNodes(result);
    const expectedTypes = new Set(DB.artifactTypes.map(at => `"${at.name}"`));
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toEqual(
      expect.arrayContaining(Array.from(expectedTypes))
    );
  });
});

describe('autosuggest project artifacts', () => {
  it('suggest project artifact name', async () => {
    const client = await testClient();
    const vNode = voidNode();

    const graph = opProjectArtifact({
      project: opRootProject({
        entityName: constString('shawn'),
        projectName: constString('dsviz_demo'),
      }),
      artifactName: vNode,
      artifactVersionAlias: vNode,
    } as any);
    const result = await autosuggest(client, vNode, graph, []);

    expectOnlyNodes(result);
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toEqual(
      expect.arrayContaining(['"train_results"'])
    );
  });
});

describe('autosuggest project artifact versions', () => {
  it('suggest project artifact version name', async () => {
    const client = await testClient();
    const vNode = voidNode();

    const graph = opProjectArtifactVersion({
      project: opRootProject({
        entityName: constString('shawn'),
        projectName: constString('dsviz_demo'),
      }),
      artifactName: vNode,
      artifactVersionAlias: vNode,
    } as any);
    const result = await autosuggest(client, vNode, graph, []);

    expectOnlyNodes(result);
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toEqual(
      expect.arrayContaining(['"train_results"'])
    );
  });
  it('suggest project artifact version numbers', async () => {
    const client = await testClient();
    const vNode = voidNode();
    const expectedArtifact = DB.artifacts[0];

    const graph = opProjectArtifactVersion({
      project: opRootProject({
        entityName: constString('shawn'),
        projectName: constString('dsviz_demo'),
      }),
      artifactName: constString(expectedArtifact.name),
      artifactVersionAlias: vNode,
    } as any);
    const result = await autosuggest(client, vNode, graph, []);

    expectOnlyNodes(result);
    const expected = new Set(
      DB.artifactVersions
        .filter(av => av.artifactId === expectedArtifact.id)
        .map(av => `"v${av.versionIndex.toString()}"`)
    );
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toEqual(
      expect.arrayContaining(Array.from(expected))
    );
  });
  it('suggest project artifact names with tag project node', async () => {
    const client = await testClient();
    const vNode = voidNode();
    const tagProjectNode = opGetProjectTag({
      obj: varNode(
        taggedValue(
          typedDict({entityName: 'string', projectName: 'string'}),
          typedDict({
            project: 'project',
            filter: 'string',
            order: 'string',
          })
        ),
        'runs'
      ),
    });

    const graph = opProjectArtifactVersion({
      project: tagProjectNode,
      artifactName: vNode,
      artifactVersionAlias: vNode,
    } as any);

    const frame = {
      runs: opProjectRuns({
        project: opRootProject({
          entityName: constString('shawn'),
          projectName: constString('dsviz_demo'),
        }),
      }),
    };

    const result = await autosuggest(
      client,
      vNode,
      graph,
      pushFrame(emptyStack(), frame)
    );

    expectOnlyNodes(result);
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toEqual(
      expect.arrayContaining(['"train_results"'])
    );
  });
  it('suggest project artifact versions with tag project node', async () => {
    const client = await testClient();
    const vNode = voidNode();
    const expectedArtifact = DB.artifacts[0];
    const tagProjectNode = opGetProjectTag({
      obj: varNode(
        taggedValue(
          typedDict({entityName: 'string', projectName: 'string'}),
          typedDict({
            project: 'project',
            filter: 'string',
            order: 'string',
          })
        ),
        'runs'
      ),
    });

    const graph = opProjectArtifactVersion({
      project: tagProjectNode,
      artifactName: constString(expectedArtifact.name),
      artifactVersionAlias: vNode,
    } as any);

    const frame = {
      runs: opProjectRuns({
        project: opRootProject({
          entityName: constString('shawn'),
          projectName: constString('dsviz_demo'),
        }),
      }),
    };

    const result = await autosuggest(
      client,
      vNode,
      graph,
      pushFrame(emptyStack(), frame)
    );

    expectOnlyNodes(result);
    const expected = new Set(
      DB.artifactVersions
        .filter(av => av.artifactId === expectedArtifact.id)
        .map(av => `"v${av.versionIndex.toString()}"`)
    );
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toEqual(
      expect.arrayContaining(Array.from(expected))
    );
  });
});

describe('autosuggest', () => {
  it('suggest for var', async () => {
    const client = await testClient();
    const node = varNode(typedDict({a: 'number', b: 'string'}), 'x');
    const result = await autosuggest(client, node, node, []);

    expectOnlyNodes(result);
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toEqual(['x["a"]', 'x["b"]', 'x[]', 'x.isNone']);
  });

  it('suggest for void node with var in frame', async () => {
    const client = await testClient();
    const inputNode = varNode(typedDict({a: 'number', b: 'string'}), 'x');
    const vNode = voidNode();
    const result = await autosuggest(
      client,
      vNode,
      vNode,
      pushFrame(emptyStack(), {x: inputNode})
    );

    expectOnlyNodes(result);
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toContain('x');
  });

  it('suggest for number', async () => {
    const client = await testClient();
    const inputNode = varNode('number', 'x');
    const vNode = voidNode();
    const result = await autosuggest(
      client,
      vNode,
      vNode,
      pushFrame(emptyStack(), {x: inputNode})
    );

    expectOnlyNodes(result);
    const autosuggestNames = suggestResultNames(result);
    expect(autosuggestNames).toContain('x');
  });

  it('suggest replacements for binary ops', async () => {
    const client = await testClient();
    const inputNode = varNode('number', 'row');
    const addOutputNode = opNumberAdd({
      lhs: inputNode,
      rhs: constNumber(3),
    });

    const addResult = await autosuggest(
      client,
      addOutputNode.fromOp,
      addOutputNode,
      pushFrame(emptyStack(), {x: inputNode})
    );

    expectOnlyOps(addResult);
    const addAutosuggestNames = addResult.map(r => r.suggestionString);

    expect(addAutosuggestNames).toEqual(['%', '*', '**', '+', '-', '/', '//']);

    const compareOutputNode = opNumberLessEqual({
      lhs: addOutputNode,
      rhs: constNumber(5),
    });

    const compareResult = await autosuggest(
      client,
      compareOutputNode.fromOp,
      compareOutputNode,
      pushFrame(emptyStack(), {x: inputNode})
    );

    expectOnlyOps(compareResult);
    const compareAutosuggestNames = compareResult.map(r => r.suggestionString);

    expect(compareAutosuggestNames).toEqual(['!=', '<', '<=', '==', '>', '>=']);
  });

  it('suggest replacements for chain ops', async () => {
    const client = await testClient();
    const inputNode = varNode(list('number'), 'x');
    const outputNode: EditingOutputNode = opNumbersAvg({
      numbers: inputNode,
    });

    const result = await autosuggest(
      client,
      outputNode.fromOp,
      outputNode,
      pushFrame(emptyStack(), {x: inputNode})
    );

    expectOnlyOps(result);
    const autosuggestNames = result.map(r => r.suggestionString);

    expect(autosuggestNames).toEqual([
      'argmax',
      'argmin',
      'avg',
      'count',
      'max',
      'min',
      'stddev',
      'sum',
    ]);
  });
});

describe('suggest for null equality', () => {
  const suggestForNumberEqualLhsType = async (type: Type) => {
    const client = await testClient();
    const vNode = voidNode();
    const inputNode = opNumberEqual({
      lhs: varNode(type, 'x'),
      rhs: vNode as any,
    });
    const result = await autosuggest(client, vNode, inputNode, []);

    expectOnlyNodes(result);
    return suggestResultNames(result);
  };
  it('number = ', async () => {
    expect(await suggestForNumberEqualLhsType('number')).toEqual(['3.14159']);
  });

  it('number | null = ', async () => {
    expect(await suggestForNumberEqualLhsType(maybe('number'))).toEqual([
      '3.14159',
      'null',
    ]);
  });

  it('List<number | null> = ', async () => {
    expect(await suggestForNumberEqualLhsType(list(maybe('number')))).toEqual([
      '3.14159',
      'null',
    ]);
  });

  it('suggestOp: number | null >= ', async () => {
    const client = await testClient();
    const inputNode = opNumberGreaterEqual({
      lhs: varNode(maybe('number'), 'x'),
      rhs: constNumber(14),
    });
    const result = await autosuggest(client, inputNode.fromOp, inputNode, []);

    expectOnlyOps(result);
    const resultNames = result.map(r => r.suggestionString);
    expect(resultNames).toEqual(['!=', '<', '<=', '==', '>', '>=']);
  });
});
