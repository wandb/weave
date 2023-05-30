import * as HL from '../../hl';
import {InputTypes, OpInputNodes, OutputNode} from '../../model/graph/types';
import {Type} from '../../model/types';
import {RefineNodeFn} from '../../opStore/types';
import {replaceInputVariables} from '../../refineHelpers';

// This function allows ops to easily make a resolveOutputType function that
// refines via another op. This is useful for ops that have sufficiently
// complicated refinement logic which we want Weave1 to handle. We don't want
// Weave1 to handle all refinement logic - since it could be more expensive.
// Therefore, this approach allows us to pick and choose which ops we want to
// handle in Weave1. Currently, this is intended to be used by various
// *table-rows type resolvers.
export const makeResolveOutputTypeFromOp = <
  I extends InputTypes,
  RT extends Type
>(
  refineOp: (inputs: OpInputNodes<I>) => OutputNode<RT>,
  inputsToRefine: string[] = []
): RefineNodeFn => {
  // This is table.ts's implementation made generic
  const resolveOutputType: RefineNodeFn = async (
    node,
    executableNode,
    client
  ) => {
    const refineNodePromises = inputsToRefine.map(inputName => {
      return HL.refineNode(
        client,
        replaceInputVariables(
          executableNode.fromOp.inputs[inputName],
          client.opStore
        ),
        // TODO: I removed client.frame... do we need that here?
        []
      );
    });
    const refineNodeResults = await Promise.all(refineNodePromises);
    const refinedInputs = {...executableNode.fromOp.inputs};
    inputsToRefine.forEach((inputName, i) => {
      refinedInputs[inputName] = refineNodeResults[i];
    });
    const newType = await client.query(refineOp(refinedInputs as any));
    return {
      ...node,
      type: newType,
    };
  };
  return resolveOutputType;
};
