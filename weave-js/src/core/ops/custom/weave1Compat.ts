/**
 * There are a number of ops that are defined only in python. In order to safely use them in
 * typescript, we want to have stubs that correctly build the graph.
 */

import {list, maybe, Node, OutputNode, Type, typedDict} from '../../model';

// This is similar to callOpVeryUnsafe, but with proper typing.
export function directlyConstructOpCall<T extends Type = 'any'>(
  opName: string,
  inputs: Record<string, Node>,
  outputType: T
): OutputNode<T> {
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

export const opFilesystemArtifactArtifactName = (inputs: {
  artifact: Node<{type: 'FilesystemArtifact'}>;
}) => {
  return directlyConstructOpCall(
    'FilesystemArtifact-artifactName',
    inputs,
    'string'
  );
};

export const opFilesystemArtifactArtifactVersion = (inputs: {
  artifact: Node<{type: 'FilesystemArtifact'}>;
}) => {
  return directlyConstructOpCall(
    'FilesystemArtifact-artifactVersion',
    inputs,
    'string'
  );
};

export const opFilesystemArtifactCreatedAt = (inputs: {
  artifact: Node<{type: 'FilesystemArtifact'}>;
}) => {
  return directlyConstructOpCall('FilesystemArtifact-createdAt', inputs, {
    type: 'timestamp',
  });
};

export const opFilesystemArtifactWeaveType = (inputs: {
  artifact: Node<{type: 'FilesystemArtifact'}>;
}) => {
  return directlyConstructOpCall(
    'FilesystemArtifact-weaveType',
    inputs,
    'type'
  );
};

export const opFilesystemArtifactMetadata = (inputs: {
  self: Node<{type: 'FilesystemArtifact'}>;
}) => {
  return directlyConstructOpCall('FilesystemArtifact-metadata', inputs, {
    type: 'typedDict',
    propertyTypes: {},
  });
};

export const opFilesystemArtifactLatestVersion = (inputs: {
  artifact: Node<{type: 'FilesystemArtifact'}>;
}) => {
  return directlyConstructOpCall(
    'FilesystemArtifact-getLatestVersion',
    inputs,
    {type: 'FilesystemArtifact'}
  );
};

// Only works on FilesystemArtifactRef right now, not generic.
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

export const opSaveToUri = (inputs: {
  obj: Node<'any'>;
  name: Node<'string'>;
}) => {
  return directlyConstructOpCall(
    '__internal__-generateCodeForObject',
    inputs,
    'string'
  );
};

export const opStreamTableRows = (inputs: {
  self: Node<{type: 'stream_table'}>;
}) => {
  return directlyConstructOpCall(
    'stream_table-rows',
    inputs,
    list(typedDict({}))
  );
};

export const opGetFeaturedBoardTemplates = (inputs: {}) => {
  return directlyConstructOpCall(
    'py_board-get_featured_board_templates',
    inputs,
    list(typedDict({}))
  );
};

export const opGetFeaturedBoardTemplatesForNode = (inputs: {
  input_node: Node;
}) => {
  return directlyConstructOpCall(
    'py_board-get_board_templates_for_node',
    inputs,
    list(typedDict({}))
  );
};

export const opRunDefaultColorIndex = (inputs: {run: Node<'run'>}) => {
  return directlyConstructOpCall('run-defaultColorIndex', inputs, 'number');
};

export const opRunHistoryLineCount = (inputs: {run: Node<'run'>}) => {
  return directlyConstructOpCall('run-historyLineCount', inputs, 'number');
};

export const opArtifactVersionDependencyOf = (inputs: {
  artifactVersion: Node<'artifactVersion'>;
}) => {
  return directlyConstructOpCall(
    'artifactVersion-dependencyOf',
    inputs,
    list('artifactVersion')
  );
};

export const opLocalArtifacts = (inputs: {}) => {
  return directlyConstructOpCall('op-local_artifacts', inputs, {
    type: 'list',
    objectType: {type: 'FilesystemArtifact'},
  });
};
