import {artifact} from '../../_external/util/urls';
import {list} from '../../model';
import {makeStandardOp} from '../opKinds';

const artifactArgTypes = {
  artifactMembership: 'artifactMembership' as const,
};

export const opArtifactMembershipId = makeStandardOp({
  hidden: true,
  name: 'artifactMembership-id',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifactMembership}) => artifactMembership.id,
});

export const opArtifactMembershipCollection = makeStandardOp({
  hidden: true,
  name: 'artifactMembership-collection',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'artifact',
  resolver: ({artifactMembership}) => artifactMembership.artifactCollection,
});

export const opArtifactMembershipArtifactVersion = makeStandardOp({
  hidden: true,
  name: 'artifactMembership-artifactVersion',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'artifactVersion',
  resolver: ({artifactMembership}) => artifactMembership.artifact,
});

export const opArtifactMembershipCreatedAt = makeStandardOp({
  hidden: true,
  name: 'artifactMembership-createdAt',
  argTypes: artifactArgTypes,
  returnType: inputTypes => ({type: 'timestamp', unit: 'ms'}),
  resolver: ({artifactMembership}) => artifactMembership.createdAt,
});

export const opArtifactMembershipCommitHash = makeStandardOp({
  hidden: true,
  name: 'artifactMembership-commitHash',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifactMembership}) => artifactMembership.commitHash,
});

export const opArtifactMembershipVersionIndex = makeStandardOp({
  hidden: true,
  name: 'artifactMembership-versionIndex',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'number',
  resolver: ({artifactMembership}) => artifactMembership.versionIndex,
});

export const opArtifactMembershipArtifactAliases = makeStandardOp({
  hidden: true,
  name: 'artifactMembership-aliases',
  argTypes: artifactArgTypes,
  returnType: inputTypes => list('artifactAlias'),
  resolver: ({artifactMembership}) => artifactMembership.aliases,
});

export const opArtifactMembershipLink = makeStandardOp({
  hidden: true,
  name: 'artifactMembership-link',
  argTypes: artifactArgTypes,
  returnType: inputTypes => 'link',
  resolver: ({artifactMembership}) => ({
    name: `${artifactMembership.artifactCollection.name}:v${artifactMembership.versionIndex}`,
    url: artifact({
      entityName: artifactMembership.artifactCollection.project.entity.name,
      projectName: artifactMembership.artifactCollection.project.name,
      artifactTypeName:
        artifactMembership.artifactCollection.defaultArtifactType.name,
      artifactSequenceName: artifactMembership.artifactCollection.name,
      artifactCommitHash: `v${artifactMembership.versionIndex}`,
    }),
  }),
});
