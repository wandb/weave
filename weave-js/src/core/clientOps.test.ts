import {callOpVeryUnsafe} from './callers';
import * as HL from './hl';
import type {Node, Type} from './model';
import {constNodeUnsafe, constNumber} from './model';
import {opNumberAdd} from './ops';
import type {ExpansionFunction} from './opStore';
import {registerGeneratedWeaveOp} from './opStore';
import {testClient} from './testUtil';

function registerPanelOp3(
  panelId: string,
  inputType: Type,
  outputType: Type,
  configuredTransform: ExpansionFunction
) {
  const name = 'panel-' + panelId;
  registerGeneratedWeaveOp({
    name,
    inputTypes: {input: inputType},
    outputType,
    expansionFn: configuredTransform,
  });
  return name;
}

describe('clientOps', () => {
  it('simple adder', async () => {
    const client = await testClient();
    const panelTransform: ExpansionFunction = (async (
      inputs: any,
      refineNode: any
    ): Promise<Node> => {
      const {input, config: configNode} = inputs;
      if (configNode.nodeType !== 'const') {
        throw new Error('invalid');
      }
      const config = configNode.val;
      return new Promise(resolve =>
        setTimeout(async () => {
          // Ensure we can recursively call refine
          const refined = await refineNode(input);
          resolve(
            opNumberAdd({
              lhs: refined as any,
              rhs: constNumber(config.rhs),
            })
          );
        }, 1)
      );
    }) as any;
    const name = registerPanelOp3(
      'testAdder',
      'number',
      'number',
      panelTransform
    );
    const outputNode = callOpVeryUnsafe(name, {
      input: constNumber(4),
      config: constNodeUnsafe('any', {rhs: 5}),
    });

    const expandedNode = await HL.expandAll(client, outputNode as any, []);
    expect(await client.query(expandedNode as any)).toEqual(9);
  });
});
