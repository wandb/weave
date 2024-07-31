import * as OpKinds from '../opKinds';

const artifactTagArgTypes = {
  artifactTag: 'artifactTag' as const,
};

export const opArtifactTagName = OpKinds.makeStandardOp({
  hidden: true,
  name: 'artifactTag-name',
  argTypes: artifactTagArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifactTag}) => artifactTag.name,
});
