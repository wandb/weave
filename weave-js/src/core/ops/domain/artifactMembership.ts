import {artifact} from '../../_external/util/urls';
import {list, maybe, union} from '../../model';
import {makeStandardOp} from '../opKinds';
import {docType} from "@wandb/weave/core/util/docs";
import * as TypeHelpers from "@wandb/weave/core/model/helpers";
import {opFileType, replaceInputVariables} from "@wandb/weave/core";
import * as _ from "lodash";

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

export const opArtifactMembershipFilesType = makeStandardOp({
  name: 'artifactMembership-_files_refine_output_type',
  argTypes: artifactArgTypes,
  description: `Returns the type of a ${docType('list')} of ${docType('file', {
    plural: true,
  })} of the ${docType('artifactMembership')}`,
  argDescriptions: {
    artifactMembership: artifactMembershipArgDescription,
  },
  hidden: true,
  returnValueDescription: `The type of a ${docType('list')} of ${docType(
      'file',
      {
        plural: true,
      }
  )} of the ${docType('artifactMembership')}`,
  returnType: inputTypes => 'type',
  resolver: async (
      {artifactMembership},
      rawInputs,
      inputTypes,
      forwardGraph,
      forwardOp,
      context
  ) => {
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      // Note these awaits happen serially!
      const result = await context.backend.getArtifactFileMetadata(
          artifactMembership.artifact.id,
          ''
      );
      if (result == null || result.type !== 'dir') {
        throw new Error('opArtifactMembershipFiles: not a directory');
      }
      // See comment in opArtifactFiles for info about how this currently works.
      const types = [];
      for (const fileName of Object.keys(result.files)) {
        const type = TypeHelpers.filePathToType(
            result.files[fileName].fullPath
        );
        types.push(type);
      }
      return list(union(types));
    } catch (e) {
      console.warn('Error loading artifact from membership', {err: e, artifactMembership});
      return list(union([]));
    }
  },
});

export const opArtifactMembershipFiles = makeStandardOp({
  name: 'artifactMembership-files',
  argTypes: artifactArgTypes,
  description: `Returns the ${docType('list')} of ${docType('file', {
    plural: true,
  })} of the ${docType('artifactMembership')}`,
  argDescriptions: {
    artifactMembership: artifactMembershipArgDescription,
  },
  returnValueDescription: `The ${docType('list')} of ${docType('file', {
    plural: true,
  })} of the ${docType('artifactMembership')}`,
  returnType: inputTypes => list({type: 'file'}),
  resolver: async (
      {artifactMembership},
      rawInputs,
      inputTypes,
      forwardGraph,
      forwardOp,
      context
  ) => {
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      // Note these awaits happen serially!
      const result = await context.backend.getArtifactFileMetadata(
          artifactMembership.artifact.id,
          ''
      );
      if (result == null || result.type !== 'dir') {
        throw new Error('opArtifactMembershipFiles: not a directory');
      }
      // See comment in opArtifactFiles for info about how this currently works.
      return Object.keys(result.files).map(path => ({
        artifact: {
          id: artifactMembership.artifact.id,
        },
        path,
      }));
    } catch (e) {
      console.warn('Error loading artifact from membership', {err: e, artifactMembership});
      return [];
    }
  },
  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    const artifactMembershipNode = replaceInputVariables(
        executableNode.fromOp.inputs.artifactMembership,
        client.opStore
    );
    const refineOp = opArtifactMembershipFilesType({
      artifactMembership: artifactMembershipNode,
    });
    let result = await client.query(refineOp);

    // This is a Weave1 hack. Weave1's type refinement ops return
    // tagged/mapped results. But the Weave0 opKinds framework is going to do
    // the same wrapping to the result we return here. So we unwrap the Weave1
    // result and let it be rewrapped.
    if (TypeHelpers.isTaggedValue(result)) {
      result = TypeHelpers.taggedValueValueType(result);
    }

    return result ?? 'none';
  },
});

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
      inputs,
      inputTypes,
      rawInputs,
      forwardGraph,
      forwardOp,
      context
  ) => {
    console.log("inside w0 op")
    // NOTE: We're passing inputs back directly, which is artifact path
    // looks like {artifact: {id: <artifact_id>}, path: <string>}
    // TODO: not final, file doesn't need to be artifact dependent
    if (inputs.artifactMembership == null) {
      throw new Error('opArtifactMembershipFile missing artifactMembership');
    }
    const file = {artifact: inputs.artifactMembership.artifact, path: inputs.path};
    const {artifact, path} = file;
    console.log(inputs.artifactMembership, path);
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileMetadata(
          artifact.id,
          path
      );
      // TODO: we should actually be storing the file metadata here, and
      // the child ops can grab it (like toGraphql). We should use
      // taggedvalue to store the artifact, instead of hard coding it. Tag
      // value will properly propagate nulls etc.
      if (result == null) {
        return null;
      }
      return {artifact: inputs.artifactMembership.artifact, path: inputs.path};
    } catch (e) {
      console.warn('Error loading artifact from membership', {err: e, artifact, path});
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
