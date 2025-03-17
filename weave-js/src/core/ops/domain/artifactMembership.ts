import {opFileType} from '@wandb/weave/core';
import * as TypeHelpers from '@wandb/weave/core/model/helpers';
import {docType} from '@wandb/weave/core/util/docs';
import * as _ from 'lodash';

import {artifact} from '../../_external/util/urls';
import {list, maybe, union} from '../../model';
import {makeStandardOp} from '../opKinds';

const artifactArgTypes = {
  artifactMembership: 'artifactMembership' as const,
};

const artifactMembershipArgDescription = `A ${docType('artifactMembership')}`;

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

// Same as opArtifactVersionFile
export const opArtifactMembershipFile = makeStandardOp({
  name: 'artifactMembership-file',
  argTypes: {...artifactArgTypes, path: 'string'},
  description: `Returns the ${docType('file')} of the ${docType(
    'artifactMembership'
  )} for the given path`,
  argDescriptions: {
    artifactMembership: artifactMembershipArgDescription,
    path: `The path of the ${docType('file')}`,
  },
  returnValueDescription: `The ${docType('file')} of the ${docType(
    'artifactMembership'
  )} for the given path`,
  returnType: inputTypes => maybe({type: 'file'}),
  resolver: async (
    {artifactMembership, path},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    if (artifactMembership == null) {
      throw new Error('opArtifactMembershipFile missing artifactMembership');
    }
    if (artifactMembership.artifact == null) {
      throw new Error('opArtifactMembershipFile missing artifact');
    }
    const artifactCollection = artifactMembership.artifactCollection;
    if (artifactCollection == null) {
      throw new Error('opArtifactMembershipFile missing artifactCollection');
    }
    try {
      const result = await context.backend.getArtifactMembershipFileMetadata(
        artifactMembership.id,
        artifactCollection.project.entityName,
        artifactCollection.project.name,
        artifactCollection.name,
        `v${artifactMembership.versionIndex}`,
        path
      );
      if (result == null) {
        return null;
      }
      return {artifact: artifactMembership.artifact, path};
    } catch (e) {
      console.warn('Error loading artifact from membership', {
        err: e,
        artifact: artifactMembership.artifact,
        path,
      });
      return null;
    }
  },
  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    const fileTypeNode = opFileType({
      file: executableNode as any,
    });
    let fileType = await client.query(fileTypeNode);

    if (fileType == null) {
      return 'none';
    }

    // The standard op pattern does not handle returning types as arrays. This
    // should be merged into standard op, but since opFileType is the only "type"
    // op, and only used here, just keeping it simple.
    // This is for Weave0
    if (_.isArray(fileType)) {
      fileType = union(fileType.map(t => (t == null ? 'none' : t)));
    }

    // This is a Weave1 hack. Weave1's type refinement ops (like file-type) return
    // tagged/mapped results. But the Weave0 opKinds framework is going to do
    // the same wrapping to the result we return here. So we unwrap the Weave1
    // result and let it be rewrapped.
    if (TypeHelpers.isTaggedValue(fileType)) {
      fileType = TypeHelpers.taggedValueValueType(fileType);
    }
    if (TypeHelpers.isList(fileType)) {
      fileType = fileType.objectType;
    }
    return fileType ?? 'none';
  },
});
