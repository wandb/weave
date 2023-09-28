import {makeOp} from '../../opStore';

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
