import {maybe, union} from '../../model';
import {makeOp} from '../../opStore';

export const opIf = makeOp({
  name: 'if',
  hidden: true,
  argTypes: {
    condition: maybe('boolean'),
    then: 'any',
    else: 'any',
  },
  kind: 'basic',
  description:
    'If the condition is true, returns the then value, otherwise returns the else value',
  argDescriptions: {
    condition: 'Condition to evaluate',
    then: 'Value to return if condition is true',
    else: 'Value to return if condition is false',
  },
  returnValueDescription:
    'If the condition is true, returns the then value, otherwise returns the else value',
  returnType: inputTypes => union([inputTypes.then.type, inputTypes.else.type]),
  resolver: ({condition, then, else: elseValue}) => {
    if (condition) {
      return then;
    } else {
      return elseValue;
    }
  },
  resolveOutputType: async (node, executableNode, client) => {
    const conditionNode = node.fromOp.inputs.condition;
    const thenNode = node.fromOp.inputs.then;
    const elseNode = node.fromOp.inputs.else;
    const condition = await client.query(conditionNode);
    let nodeType = node.type;
    if (condition) {
      nodeType = thenNode.type;
    } else {
      nodeType = elseNode.type;
    }
    return {
      ...node,
      type: nodeType,
    };
  },
});

// NEVER expose this op externally. The reason it
// exists is to act as a barrier between lambda
// functions and the rest of the graph. This allows
// us to associate downstream ops with their
// upstream providers for GQL generation, without
// adding it to the tree formally, reducing nodes
// traversed in the graph during other execution paths.
export const opLambdaClosureArgBridge = makeOp({
  hidden: true,
  name: 'internal-lambdaClosureArgBridge',
  argTypes: {arg: 'any'},
  description: '',
  argDescriptions: {arg: ''},
  returnValueDescription: '',
  returnType: inputs => inputs.arg.type,
  resolver: inputs => inputs.arg,
});
