import {opArtifactProject, opIsNone} from '@wandb/weave/core';
import * as _ from 'lodash';

import * as Urls from '../../_external/util/urls';
import {
  BASIC_MEDIA_TYPES,
  list,
  mappableNullableTaggableVal,
  maybe,
  Type,
  typedDict,
  union,
} from '../../model';
import {constNumber, constString} from '../../model/graph/construction';
import * as TypeHelpers from '../../model/helpers';
import {replaceInputVariables} from '../../refineHelpers';
import {docType} from '../../util/docs';
import {JSONparseNaN} from '../../util/jsonnan';
import {makeBasicOp, makeStandardOp} from '../opKinds';
import {opDict} from '../primitives/literals';
import {opEntityName} from './entity';
import {opFileType} from './file';
import {opProjectEntity, opProjectName, opProjectRun} from './project';
import {opRootProject} from './root';
import {
  opRunHistoryAsOfStep,
  opRunId,
  opRunProject,
  wandbJsonType,
  wandbJsonWithArtifacts,
} from './run';
import {connectionToNodes} from './util';

const makeArtifactVersionOp = makeStandardOp;

const artifactVersionArgTypes = {
  artifactVersion: 'artifactVersion' as const,
};

const artifactVersionArgDescription = `A ${docType('artifactVersion')}`;

export const opArtifactVersionName = makeArtifactVersionOp({
  name: 'artifactVersion-name',
  argTypes: artifactVersionArgTypes,
  description: `Returns the name of the ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The name of the ${docType('artifactVersion')}`,
  returnType: inputTypes => 'string',
  resolver: ({artifactVersion}) =>
    artifactVersion.artifactSequence.name + ':v' + artifactVersion.versionIndex,
});

export const opArtifactVersionState = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-state',
  argTypes: artifactVersionArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifactVersion}) => artifactVersion.state,
});

export const opArtifactVersionDigest = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-digest',
  argTypes: artifactVersionArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifactVersion}) => artifactVersion.digest,
});

export const opArtifactVersionDescription = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-description',
  argTypes: artifactVersionArgTypes,
  returnType: inputTypes => 'string',
  resolver: ({artifactVersion}) => artifactVersion.description,
});

export const opArtifactVersionVersionId = makeArtifactVersionOp({
  name: 'artifactVersion-versionId',
  argTypes: artifactVersionArgTypes,
  description: `Returns the versionId of the ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The versionId of the ${docType('artifactVersion')}`,
  returnType: inputTypes => 'number',
  resolver: ({artifactVersion}) => artifactVersion.versionIndex,
});

// Do not make this public, ID ops shouldn't be public! They are
// useful for debugging, but users shouldn't need our gqlIds.
export const opArtifactVersionId = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-id',
  argTypes: artifactVersionArgTypes,
  description: `Returns the id of the ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The id of the ${docType('artifactVersion')}`,
  returnType: inputTypes => 'string',
  resolver: ({artifactVersion}) => artifactVersion.id,
});

export const opArtifactVersionSize = makeArtifactVersionOp({
  name: 'artifactVersion-size',
  argTypes: artifactVersionArgTypes,
  description: `Returns the size of the ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The size of the ${docType('artifactVersion')}`,
  returnType: inputTypes => 'number',
  resolver: ({artifactVersion}) => artifactVersion.size,
});

export const opArtifactVersionTTLDurationSeconds = makeArtifactVersionOp({
  name: 'artifactVersion-ttlDurationSeconds',
  argTypes: artifactVersionArgTypes,
  description: `Returns the original duration in seconds that a ${docType(
    'artifactVersion'
  )} is expected to live for before it gets deleted`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The original duration in seconds that an ${docType(
    'artifactVersion'
  )} is expected to live for before it gets deleted`,
  returnType: inputTypes => 'number',
  resolver: ({artifactVersion}) => artifactVersion.ttlDurationSeconds,
});

export const opArtifactVersionTTLIsInherited = makeArtifactVersionOp({
  name: 'artifactVersion-ttlIsInherited',
  argTypes: artifactVersionArgTypes,
  description: `Returns if the artifact TTL is inherited ${docType(
    'artifactVersion'
  )}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `Returns if the artifact TTL is inherited ${docType(
    'artifactVersion'
  )}`,
  returnType: inputTypes => 'boolean',
  resolver: ({artifactVersion}) => artifactVersion.ttlIsInherited,
});

export const opArtifactVersionCreatedAt = makeArtifactVersionOp({
  name: 'artifactVersion-createdAt',
  argTypes: artifactVersionArgTypes,
  description: `Returns the datetime at which the ${docType(
    'artifactVersion'
  )} was created`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The datetime at which the ${docType(
    'artifactVersion'
  )} was created`,
  returnType: inputTypes => ({type: 'timestamp', unit: 'ms'}),
  resolver: ({artifactVersion}) => artifactVersion.createdAt,
});

export const opArtifactVersionFileCount = makeArtifactVersionOp({
  name: 'artifactVersion-fileCount',
  argTypes: artifactVersionArgTypes,
  description: `Returns the file count of the artifact ${docType(
    'artifactVersion'
  )}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `Returns the file count of the artifact ${docType(
    'artifactVersion'
  )}`,
  returnType: inputTypes => 'number',
  resolver: ({artifactVersion}) => artifactVersion.fileCount,
});

export const opArtifactVersionFiles = makeArtifactVersionOp({
  name: 'artifactVersion-files',
  argTypes: artifactVersionArgTypes,
  description: `Returns the ${docType('list')} of ${docType('file', {
    plural: true,
  })} of the ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The ${docType('list')} of ${docType('file', {
    plural: true,
  })} of the ${docType('artifactVersion')}`,
  returnType: inputTypes => list({type: 'file'}),
  resolver: async (
    {artifactVersion},
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
        artifactVersion.id,
        ''
      );
      if (result == null || result.type !== 'dir') {
        throw new Error('opArtifactVersionFiles: not a directory');
      }
      // See comment in opArtifactFiles for info about how this currently works.
      return Object.keys(result.files).map(path => ({
        artifact: {
          id: artifactVersion.id,
        },
        path,
      }));
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifactVersion});
      return [];
    }
  },
});

export const opArtifactVersionIsGenerated = makeArtifactVersionOp({
  name: 'artifactVersion-isGenerated',
  argTypes: artifactVersionArgTypes,
  description: `Returns if the artifact is system-generated ${docType(
    'artifactVersion'
  )}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `Returns if the artifact is system-generated ${docType(
    'artifactVersion'
  )}`,
  returnType: inputTypes => 'boolean',
  resolver: ({artifactVersion}) => artifactVersion.isGenerated,
});

export const opArtifactVersionIsLinkedToGlobalRegistry = makeArtifactVersionOp({
  name: 'artifactVersion-isLinkedToGlobalRegistry',
  argTypes: artifactVersionArgTypes,
  description: `Returns if the artifact is linked to a collection in the global registry ${docType(
    'artifactVersion'
  )}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `Returns if the artifact is linked to a collection in the global registry ${docType(
    'artifactVersion'
  )}`,
  returnType: inputTypes => 'boolean',
  resolver: ({artifactVersion}) => artifactVersion.isLinkedToGlobalRegistry,
});

const mediaTypeExtensions = BASIC_MEDIA_TYPES.map(mediaType => mediaType.type);
const isMediaFilePath = (path: string) =>
  mediaTypeExtensions.some(extension => path.endsWith(`.${extension}.json`));

export const opArtifactVersionDefaultFile = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-defaultFile',
  argTypes: artifactVersionArgTypes,
  returnType: inputTypes => maybe({type: 'file'}),
  resolver: async (
    {artifactVersion},
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
        artifactVersion.id,
        ''
      );
      if (result == null || result.type !== 'dir') {
        throw new Error('opArtifactVersionDefaultFile: not a directory');
      }
      let backupPath: string | null = null;
      let mainPath: string | null = null;
      for (const path in result.files) {
        if (path.indexOf('/') === -1) {
          if (isMediaFilePath(path)) {
            if (path.startsWith('index')) {
              mainPath = path;
              break;
            } else {
              backupPath = path;
            }
          }
        }
      }

      const targetPath = mainPath ?? backupPath;

      if (targetPath != null) {
        return {
          artifact: {
            id: artifactVersion.id,
          },
          path: targetPath,
        };
      }

      return null;
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifactVersion});
      return null;
    }
  },
});

export const opArtifactVersionFile = makeArtifactVersionOp({
  name: 'artifactVersion-file',
  argTypes: {...artifactVersionArgTypes, path: 'string'},
  description: `Returns the ${docType('file')} of the ${docType(
    'artifactVersion'
  )} for the given path`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
    path: `The path of the ${docType('file')}`,
  },
  returnValueDescription: `The ${docType('file')} of the ${docType(
    'artifactVersion'
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
    // NOTE: We're passing inputs back directly, which is artifact path
    // looks like {artifact: {id: <artifact_id>}, path: <string>}
    // TODO: not final, file doesn't need to be artifact dependent
    if (inputs.artifactVersion == null) {
      throw new Error('opArtifactVersionFile missing artifactVersion');
    }
    const file = {artifact: inputs.artifactVersion, path: inputs.path};
    const {artifact, path} = file;
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
      return {artifact: inputs.artifactVersion, path: inputs.path};
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
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

// TODO: We shouldn't expose special *Count ops, instead the user can
// call opCount on whatever array
export const opArtifactVersionReferenceCount = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-referenceCount',
  argTypes: artifactVersionArgTypes,
  description: `Returns the count of references to the ${docType(
    'artifactVersion'
  )}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The count of references to the ${docType(
    'artifactVersion'
  )}`,
  returnType: inputTypes => 'number',
  resolver: ({artifactVersion}) => artifactVersion.usedCount,
});

export const opArtifactVersionUsedBy = makeArtifactVersionOp({
  name: 'artifactVersion-usedBy',
  argTypes: artifactVersionArgTypes,
  description: `Returns the ${docType('run', {
    plural: true,
  })} that use the ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The ${docType('run', {
    plural: true,
  })} that use the ${docType('artifactVersion')}`,
  returnType: inputTypes => list('run'),
  resolver: ({artifactVersion}) => connectionToNodes(artifactVersion.usedBy),
});

// TODO: These two comprise a good example of a missing part of Weave.
// We can't realistically make an op that returns a union of user
// and run, and then make meaningful ops downstream. We need to
// switch on the type somehow.
export const opArtifactVersionCreatedBy = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-createdBy',
  argTypes: artifactVersionArgTypes,
  description: `Returns the ${docType('run')} that created the ${docType(
    'artifactVersion'
  )}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The ${docType('run')} that created the ${docType(
    'artifactVersion'
  )}`,
  returnType: inputTypes => maybe('run'),
  resolver: ({artifactVersion}) => {
    // Currently only supports Run-created artifacts.
    if (artifactVersion.createdByRun?.__typename === 'Run') {
      return artifactVersion.createdByRun;
    }
    return null;
  },
});

export const opArtifactVersionCreatedByUser = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-createdByUser',
  argTypes: artifactVersionArgTypes,
  description: `Returns the ${docType('user')} that created the ${docType(
    'artifactVersion'
  )}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The ${docType('user')} that created the ${docType(
    'artifactVersion'
  )}`,
  returnType: inputTypes => maybe('user'),
  resolver: ({artifactVersion}) => {
    // Currently only supports User-created artifacts.
    if (artifactVersion.createdByUser?.__typename === 'User') {
      return artifactVersion.createdByUser;
    }
    return null;
  },
});

export const opArtifactVersionMetadata = makeArtifactVersionOp({
  name: 'artifactVersion-metadata',
  argTypes: artifactVersionArgTypes,
  description: `Returns the ${docType('artifactVersion')} metadata dictionary`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The ${docType(
    'artifactVersion'
  )} metadata dictionary`,
  returnType: inputTypes => typedDict({}),
  resolver: ({artifactVersion}) => {
    const res =
      artifactVersion.metadata !== null
        ? JSONparseNaN(artifactVersion.metadata) ?? {}
        : {};
    return wandbJsonWithArtifacts(res);
  },
  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    const metadataNode = replaceInputVariables(executableNode, client.opStore);
    const metadata = await client.query(metadataNode);

    if (metadata == null || metadata.length === 0) {
      return typedDict({});
    }

    const summary: any = metadata[0];
    if (_.isArray(summary)) {
      if (summary.length === 0) {
        // This will happen in cases that the incoming list is empty!
        return typedDict({});
      }
      return union(summary.map(wandbJsonType));
    } else {
      return wandbJsonType(summary);
    }
  },
});

const versionRegex = /^v(\d+)$/;
export const opArtifactVersionAliases = makeArtifactVersionOp({
  name: 'artifactVersion-aliases',
  argTypes: {...artifactVersionArgTypes, hideVersions: 'boolean'},
  description: `Returns the aliases for a ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The aliases for a ${docType('artifactVersion')}`,
  returnType: inputTypes => list('artifactAlias'),
  resolver: ({artifactVersion, hideVersions}) =>
    (artifactVersion.aliases ?? []).filter(
      (a: any) => a != null && (!hideVersions || !versionRegex.test(a.alias))
    ),
});

export const opArtifactVersionRawTags = makeArtifactVersionOp({
  name: 'artifactVersion-rawTags',
  argTypes: artifactVersionArgTypes,
  description: `Returns the tags for a ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The tags for a ${docType('artifactVersion')}`,
  returnType: inputTypes =>
    list(
      typedDict({
        id: 'string',
        name: 'string',
        tagCategoryName: 'string',
        attributes: 'string',
      })
    ),
  resolver: ({artifactVersion}) => artifactVersion.tags ?? [],
});

export const opArtifactVersionLink = makeArtifactVersionOp({
  name: 'artifactVersion-link',
  argTypes: artifactVersionArgTypes,
  description: `Returns the url for a ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The url for a ${docType('artifactVersion')}`,
  returnType: inputTypes => 'link',
  resolver: ({artifactVersion}) => {
    return {
      name: `${artifactVersion.artifactSequence.name}:v${artifactVersion.versionIndex}`,
      url: Urls.artifact({
        entityName: artifactVersion.artifactSequence.project.entity.name,
        projectName: artifactVersion.artifactSequence.project.name,
        artifactTypeName: artifactVersion.artifactType.name,
        artifactSequenceName: artifactVersion.artifactSequence.name,
        artifactCommitHash: artifactVersion.commitHash,
      }),
    };
  },
});

export const opArtifactVersionHash = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-hash',
  argTypes: artifactVersionArgTypes,
  description: `Returns the hash for a ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The hash for a ${docType('artifactVersion')}`,
  returnType: inputTypes => 'string',
  resolver: ({artifactVersion}) => {
    return artifactVersion.commitHash;
  },
});

export const opArtifactVersionArtifactSequence = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-artifactSequence',
  argTypes: artifactVersionArgTypes,
  description: `Returns the artifactSequence for a ${docType(
    'artifactVersion'
  )}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The artifactSequence for a ${docType(
    'artifactVersion'
  )}`,
  returnType: inputTypes => 'artifact',
  resolver: ({artifactVersion}) => {
    return artifactVersion.artifactSequence;
  },
});

export const opArtifactVersionArtifactType = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-artifactType',
  argTypes: artifactVersionArgTypes,
  description: `Returns the type for a ${docType('artifactVersion')}`,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: `The type for a ${docType('artifactVersion')}`,
  returnType: inputTypes => 'artifactType',
  resolver: ({artifactVersion}) => {
    // console.log({artifactVersion});
    return artifactVersion.artifactType;
  },
});

export const opArtifactVersionUpdateAliasActions = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-updateAliasActions',
  argTypes: artifactVersionArgTypes,
  description: ``,
  argDescriptions: {
    artifactVersion: artifactVersionArgDescription,
  },
  returnValueDescription: ``,
  returnType: inputTypes =>
    typedDict({
      // createdAt: '2021-07-30T20:48:13', oldAliases: [], newAliases: null
    }),
  resolver: ({artifactVersion}) => {
    return connectionToNodes(artifactVersion?.artifactActions).filter(
      (n: any) =>
        n.__typename === 'UpdateArtifactAction' &&
        (n.newAliases != null || n.oldAliases != null)
    );
  },
});

export const opArtifactVersionCollections = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-artifactCollections',
  argTypes: artifactVersionArgTypes,
  returnType: inputTypes => list('artifact'),
  resolver: ({artifactVersion}) =>
    connectionToNodes(artifactVersion.artifactCollections),
});

export const opArtifactVersionMemberships = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-memberships',
  argTypes: artifactVersionArgTypes,
  returnType: inputTypes => list('artifactMembership'),
  resolver: ({artifactVersion}) =>
    connectionToNodes(artifactVersion.artifactMemberships),
});

export const opArtifactVersionHistoryStep = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-historyStep',
  argTypes: artifactVersionArgTypes,
  returnType: inputTypes => maybe('number'),
  resolver: ({artifactVersion}) => artifactVersion.historyStep,
});

export const opArtifactVersionIsWeaveObject = makeArtifactVersionOp({
  hidden: true,
  name: 'artifactVersion-isWeaveObject',
  argTypes: artifactVersionArgTypes,
  returnType: inputTypes => 'boolean',
  resolver: async (
    {artifactVersion},
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
        artifactVersion.id,
        ''
      );
      if (result == null || result.type !== 'dir') {
        throw new Error('opArtifactVersionFiles: not a directory');
      }
      // See comment in opArtifactFiles for info about how this currently works.
      return Object.keys(result.files).some(path =>
        path.endsWith('obj.type.json')
      );
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifactVersion});
      return false;
    }
  },
});

// The fact that we need this is due to a flaw in our Weave <> GQL design layer
export const opArtifactVersionRunHistoryRow = makeBasicOp({
  hidden: true,
  name: 'artifactVersion-historyMetrics',
  argTypes: {
    artifactVersion: TypeHelpers.nullableOneOrMany('artifactVersion' as const),
  },
  returnType: inputTypes =>
    mappableNullableTaggableVal(inputTypes, v => typedDict({})),
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    const eng = engine();
    // With org-level registries allowing access to team-level artifacts,
    // there are cases where users can have access to the artifact,
    // but not its source run or project/team. This access check on the frontend
    // will prevent us from making queries that we know will crash for such users.
    const noProjectAccessNode = opIsNone({
      val: opArtifactProject({
        artifact: opArtifactVersionArtifactSequence({
          artifactVersion: forwardOp.op.inputs.artifactVersion,
        }),
      }),
    });
    const [noProjectAccess] = await eng.executeNodes([noProjectAccessNode]);
    if (noProjectAccess) {
      return Promise.resolve({});
    }
    const createdByRunNode = opArtifactVersionCreatedBy({
      artifactVersion: forwardOp.op.inputs.artifactVersion,
    });
    const createdByRunProjectNode = opRunProject({run: createdByRunNode});
    const createdByRunProjectEntityNode = opProjectEntity({
      project: createdByRunProjectNode,
    });
    const rootDataNode = opDict({
      historyStep: opArtifactVersionHistoryStep({
        artifactVersion: forwardOp.op.inputs.artifactVersion,
      }),
      runName: opRunId({run: createdByRunNode}),
      projectName: opProjectName({project: createdByRunProjectNode}),
      entityName: opEntityName({entity: createdByRunProjectEntityNode}),
    } as any);

    const [rootDataResult] = await eng.executeNodes([rootDataNode]);
    if (_.isArray(rootDataResult.runName)) {
      const historyNodes = rootDataResult.runName.map(
        (runName: string, index: number) => {
          const historyStep = rootDataResult.historyStep[index];
          const projectName = rootDataResult.projectName[index];
          const entityName = rootDataResult.entityName[index];
          if (historyStep == null) {
            return opDict({} as any);
          }
          return opRunHistoryAsOfStep({
            run: opProjectRun({
              project: opRootProject({
                entityName: constString(entityName),
                projectName: constString(projectName),
              }),
              runName: constString(runName),
            }),
            asOfStep: constNumber(Math.max(0, historyStep - 1)),
          });
        }
      );
      return eng.executeNodes(historyNodes);
    } else {
      if (rootDataResult == null || rootDataResult.historyStep == null) {
        return Promise.resolve({});
      }
      const historyAsOf = (
        await eng.executeNodes([
          opRunHistoryAsOfStep({
            run: opProjectRun({
              project: opRootProject({
                entityName: constString(rootDataResult.entityName),
                projectName: constString(rootDataResult.projectName),
              }),
              runName: constString(rootDataResult.runName),
            }),
            asOfStep: constNumber(Math.max(0, rootDataResult.historyStep - 1)),
          }),
        ])
      )[0];
      return historyAsOf;
    }
  },
  resolveOutputType: async (inputTypes, node, executableNode, client) => {
    const wrapper = (t: Type) => {
      if (TypeHelpers.isListLike(inputTypes.artifactVersion)) {
        return list(t);
      } else {
        return t;
      }
    };

    const resultNode = replaceInputVariables(executableNode, client.opStore);
    const result = await client.query(resultNode);

    if (result == null || result.length === 0) {
      return typedDict({});
    }

    const res = result;
    if (_.isArray(res)) {
      if (res.length === 0) {
        return wrapper(typedDict({}));
      }
      return wrapper(union(res.map(wandbJsonType)));
    } else {
      return wandbJsonType(res);
    }
  },
});
