/**
 * There are a number of ops that are defined only in python. In order to safely use them in
 * typescript, we want to have stubs that correctly build the graph.
 */

import {Node, Type, list, maybe, typedDict} from '../../model';
import {SpanWeaveWithTimestampType} from '../../../components/Panel2/PanelTraceTree/util';

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
  return directlyConstructOpCall('FilesystemArtifact-file', inputs, {
    type: 'file',
  });
};

export const opFilesystemArtifactRootFromUri = (inputs: {
  uri: Node<'string'>;
}) => {
  return directlyConstructOpCall('FilesystemArtifact-rootFromURI', inputs, {
    type: 'FilesystemArtifact',
  });
};

export const opFilesystemArtifactPreviousUri = (inputs: {
  artifact: Node<{type: 'FilesystemArtifact'}>;
}) => {
  return directlyConstructOpCall(
    'FilesystemArtifact-previousURI',
    inputs,
    'string'
  );
};

export const opRef = (inputs: {uri: Node<'string'>}) => {
  return directlyConstructOpCall('ref', inputs, {
    type: 'FilesystemArtifactRef',
  });
};

export const opRefBranchPoint = (inputs: {
  ref: Node<{type: 'FilesystemArtifactRef'}>;
}) => {
  return directlyConstructOpCall(
    'Ref-branch_point',
    inputs,
    maybe(typedDict({}))
  );
};

export const opGenerateCodeForObject = (inputs: {obj: Node<'any'>}) => {
  return directlyConstructOpCall(
    '__internal__-generateCodeForObject',
    inputs,
    'string'
  );
};


export const opSaveToUri= (inputs: {obj: Node<'any'>, name:Node<'string'>}) => {
    return directlyConstructOpCall(
      '__internal__-generateCodeForObject',
      inputs,
      'string'
    );
  };


  export const opWBTraceTreeConvertToSpans = (inputs: {tree: Node<{type: 'wb_trace_tree'}>}) => {
    return directlyConstructOpCall(
        'wb_trace_tree-convertToSpans',
        inputs,
        list(list(SpanWeaveWithTimestampType))
      );
  }
