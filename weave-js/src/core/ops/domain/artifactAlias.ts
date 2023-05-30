import * as OpKinds from '../opKinds';

const artifactAliasArgTypes = {
  artifactAlias: 'artifactAlias' as const,
};

export const opArtifactAliasAlias = OpKinds.makeStandardOp({
  hidden: true,
  name: 'artifactAlias-alias',
  argTypes: artifactAliasArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifactAlias}) => artifactAlias.alias,
});

export const opArtifactAliasArtifact = OpKinds.makeStandardOp({
  hidden: true,
  name: 'artifactAlias-artifact',
  argTypes: artifactAliasArgTypes,
  returnType: inputTypes => 'artifact',
  resolver: ({artifactAlias}) => artifactAlias.artifactCollection,
});
