/**
 * There are a number of ops that are defined only in python. In order to safely use them in
 * typescript, we want to have stubs that correctly build the graph.
 */

import { Node, Type, maybe, typedDict } from "../../model";

// This is similar to callOpVeryUnsafe, but with proper typing.
function directlyConstructOpCall<T extends Type = 'any'>(
    opName: string,
    inputs: Record<string, Node>,
    outputType: T
  ): Node<T> {
    return {
      nodeType: 'output',
      type: outputType,
      fromOp: {
        name: opName,
        inputs,
      },
    };
  }

export const opFilesystemArtifactFile = (inputs: {
    artifactVersion: Node<{type: 'FilesystemArtifact'}>;
    path: Node<'string'>;
  }) => {
    return directlyConstructOpCall(
      'FilesystemArtifact-file',
      inputs,
      {type: 'file'}
    );
  };
  

export const opRef = (inputs: {uri: Node<'string'>}) => {
    return directlyConstructOpCall(
        'ref',
        inputs,
        {type: 'FilesystemArtifactRef'}
      )
}

export const opRefBranchPoint = (inputs: {ref: Node<{type: 'FilesystemArtifactRef'}>}) => {
    return directlyConstructOpCall(
        'Ref-branch_point',
        inputs,
        maybe(typedDict({}))
      )
}
