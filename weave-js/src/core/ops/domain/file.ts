import * as _ from 'lodash';

import {
  concreteTaggedValue,
  filePathToType,
  getActualNamedTagFromValue,
  isFile,
  isTaggedValue,
  maybe,
  taggableValAsync,
  taggedValue,
  typedDict,
  withFileTag,
} from '../../model';
import {ALL_DIR_TYPE, TaggedValueType, Type} from '../../model/types';
import {docType} from '../../util/docs';
import {makeStandardOp, makeTagConsumingStandardOp} from '../opKinds';

// This function transforms bad JSON into usable JSON. In particular,
// JSON that uses the raw `Infinity` representation. Python's JSON
// serializer actually outputs the text `Infinity` which is invalid JSON.
// https://docs.python.org/3/library/json.html#standard-compliance-and-interoperability
const memoJSONParseSafe = _.memoize((text: string) => {
  const inf = 'Infinity';
  const infReplace = '___wb___Infinity___wb___';
  const ninf = '-Infinity';
  const ninfReplace = '___wb___-Infinity___wb___';
  let quoteCount = 0;

  for (let i = 0; i < text.length; i++) {
    if (
      text[i] === '"' &&
      (i === 0 || text[i - 1] !== '\\' || (i > 1 && text[i - 2] === '\\'))
    ) {
      quoteCount++;
    } else if (quoteCount % 2 === 0) {
      if (
        text[i] === inf[0] &&
        i + inf.length <= text.length &&
        text.substring(i, i + inf.length) === inf
      ) {
        text =
          text.slice(0, i) +
          '"' +
          infReplace +
          '"' +
          text.slice(i + inf.length, text.length);
        i += 1 + infReplace.length;
      } else if (
        text[i] === ninf[0] &&
        i + ninf.length <= text.length &&
        text.substring(i, i + ninf.length) === ninf
      ) {
        text =
          text.slice(0, i) +
          '"' +
          ninfReplace +
          '"' +
          text.slice(i + ninf.length, text.length);
        i += 1 + ninfReplace.length;
      }
    }
  }
  const res = JSON.parse(text, (key, val) => {
    if (val === infReplace) {
      return Infinity;
    } else if (val === ninfReplace) {
      return -Infinity;
    }
    return val;
  });

  return res;
});

const makeFileOp = makeStandardOp;

const fileArgTypes = {
  file: {type: 'file' as const},
};

const fileArgDescription = `A ${docType('file')}`;

export const opFileType = makeFileOp({
  hidden: true,
  name: 'file-type',
  argTypes: fileArgTypes,
  description: `Returns the type of the ${docType('file')}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The type of the ${docType('file')}`,
  returnType: inputTypes => maybe('type'),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileMetadata(
        artifact.id,
        path
      );
      let typeResult: Type = 'none';
      if (result != null) {
        if (result.type === 'dir') {
          typeResult = {type: 'dir' as const};
        } else {
          typeResult = filePathToType(path);
        }
      }
      return typeResult;
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

export const opFileDir = makeFileOp({
  hidden: true,
  name: 'file-dir',
  argTypes: fileArgTypes,
  description: `Returns the ${docType('dir')} of the ${docType('file')}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The ${docType('dir')} of the ${docType('file')}`,
  returnType: inputTypes => maybe({type: 'dir'}),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    // const {artifactVersion} = inputs;
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileMetadata(
        artifact.id,
        path
      );
      if (result == null) {
        return undefined;
        // throw new Error('didnt load table contents (opArtifactsTable)');
      }
      if (result.type !== 'dir') {
        throw new Error('expected dir');
      }
      return result;
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

export const opDirAsW0Dict = makeFileOp({
  hidden: true,
  name: 'dir-_as_w0_dict_',
  argTypes: {
    dir: ALL_DIR_TYPE,
  },
  returnType: inputs => typedDict({}),
  resolver: ({dir}) => {
    // In Weave0, this is identity
    return dir;
  },
});

export const opFilePath = makeFileOp({
  hidden: true,
  name: 'file-path',
  argTypes: fileArgTypes,
  description: `Returns the path of the ${docType('file')}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The path of the ${docType('file')}`,
  returnType: inputTypes => 'string',
  resolver: ({file}) => file.path,
});

export const opFileSize = makeFileOp({
  name: 'file-size',
  argTypes: fileArgTypes,
  description: `Returns the size of the ${docType('file')}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The size of the ${docType('file')}`,
  returnType: inputTypes => maybe('number'),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileMetadata(
        artifact.id,
        path
      );
      if (result == null) {
        return undefined;
        // throw new Error('didnt load table contents (opArtifactsTable)');
      }
      if (result.type === 'dir') {
        throw new Error('expected file');
      }
      return result.size;
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

export const opFileDigest = makeFileOp({
  name: 'file-digest',
  argTypes: fileArgTypes,
  description: `Returns the digest of the ${docType('file')}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The digest of the ${docType('file')}`,
  returnType: inputTypes => maybe('string'),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileMetadata(
        artifact.id,
        path
      );
      if (result == null) {
        return undefined;
      }
      if (result.type === 'dir') {
        throw new Error('expected file');
      }
      return result.digest;
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

export const opFileTable = makeTagConsumingStandardOp({
  name: 'file-table',
  argTypes: fileArgTypes,
  description: `Returns the contents of the ${docType('file')} as a ${docType(
    'table'
  )}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The contents of the ${docType(
    'file'
  )} as a ${docType('table')}`,
  returnType: inputTypes =>
    taggedValue(
      isTaggedValue(inputTypes.file)
        ? (inputTypes.file as TaggedValueType).tag
        : null,
      withFileTag(maybe({type: 'table', columnTypes: {}}), {
        type: 'file',
        extension: 'json',
        wbObjectType: {type: 'table', columnTypes: {}},
      })
    ),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    return taggableValAsync(file, async fileVal => {
      let tableValue: any;
      let tableTag = {
        file: fileVal,
      };
      const {artifact, path} = fileVal;
      if (artifact == null) {
        const runTag = getActualNamedTagFromValue(file, 'run');
        const entityNameTag = getActualNamedTagFromValue(file, 'entityName');
        const projectNameTag = getActualNamedTagFromValue(file, 'projectName');
        if (
          runTag?.run?.name &&
          entityNameTag?.entityName &&
          projectNameTag?.projectName
        ) {
          const fileContents = await context.backend.getRunFileContents(
            projectNameTag.projectName,
            runTag.run.name,
            path,
            entityNameTag.entityName
          );
          if (fileContents.contents != null) {
            try {
              tableValue = memoJSONParseSafe(fileContents.contents);
            } catch (e) {
              console.warn('Error parsing table contents', fileVal);
            }
          }
        }
      } else if (artifact != null) {
        try {
          // This errors if the sequence has been deleted (or a race case in which
          // the artifact is not created before the history step referencing it comes in)
          const {refFileId, contents} =
            await context.backend.getArtifactFileContents(artifact.id, path);
          if (contents != null) {
            try {
              tableValue = memoJSONParseSafe(contents);
              if (refFileId != null) {
                tableTag = {
                  file: {
                    artifact: {id: refFileId.artifactId},
                    path: refFileId.path,
                  },
                };
              }
            } catch (e) {
              console.warn('Error parsing table contents', fileVal);
            }
          }
        } catch (e) {
          console.warn('Error loading artifact', {err: e, artifact, path});
        }
      }
      return concreteTaggedValue(tableTag, tableValue);
    });
  },
});

export const opFileJoinedTable = makeFileOp({
  name: 'file-joinedTable',
  argTypes: {
    file: maybe({
      type: 'file',
      extension: 'json',
      wbObjectType: {type: 'joined-table', columnTypes: {}},
    }),
  },
  description: `Returns the contents of the ${docType('file')} as a ${docType(
    'joined-table'
  )}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The contents of the ${docType(
    'file'
  )} as a ${docType('joined-table')}`,
  returnType: inputTypes => maybe({type: 'joined-table', columnTypes: {}}),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileContents(
        artifact.id,
        path
      );
      const contents = result.contents;
      if (contents == null) {
        return undefined;
      }
      const joinedTable = memoJSONParseSafe(contents);
      return {artifact: {id: artifact.id}, path, joinedTable};
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

export const opFilePartitionedTable = makeFileOp({
  name: 'file-partitionedTable',
  argTypes: {
    file: maybe({
      type: 'file',
      extension: 'json',
      wbObjectType: {type: 'partitioned-table', columnTypes: {}},
    }),
  },
  description: `Returns the contents of the ${docType('file')} as a ${docType(
    'partitioned-table'
  )}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The contents of the ${docType(
    'file'
  )} as a ${docType('partitioned-table')}`,
  returnType: inputTypes => maybe({type: 'partitioned-table', columnTypes: {}}),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileContents(
        artifact.id,
        path
      );
      const contents = result.contents;
      if (contents == null) {
        return undefined;
      }
      const partitionedTable = memoJSONParseSafe(contents);
      return {artifact: {id: artifact.id}, path, partitionedTable};
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

export const opFileContents = makeFileOp({
  name: 'file-contents',
  argTypes: fileArgTypes,
  description: `Returns the contents of the ${docType('file')}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The contents of the ${docType('file')}`,
  returnType: inputTypes => maybe('string'),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileContents(
        artifact.id,
        path
      );
      const contents = result.contents;
      if (contents == null) {
        return undefined;
        // throw new Error('didnt load table contents (opArtifactsTable)');
      }
      return contents;
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

// Don't expose this. These urls expire so they have to be used carefully.
export const opFileDirectUrl = makeFileOp({
  hidden: true,
  name: 'file-directUrl',
  argTypes: fileArgTypes,
  description: `Returns the direct url of the ${docType('file')}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The direct url of the ${docType('file')}`,
  returnType: inputTypes => maybe('string'),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileDirectUrl(
        artifact.id,
        path
      );
      return result.directUrl;
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

// Don't expose this. This op accepts an `asOf` parameter, which in practice
// can be used to ensure that we do not return cached results. Be careful when
// using this op - see PanelTrace.tsx/useDirectUrlNodeWithExpiration for an
// example.
export const opFileDirectUrlAsOf = makeFileOp({
  hidden: true,
  name: 'file-directUrlAsOf',
  argTypes: {...fileArgTypes, asOf: 'number'},
  description: `Returns the direct url of the ${docType(
    'file'
  )}. The \`asOf\` parameter can be used to ensure that we do not return cached results - modify the \`asOf\` parameter to force a new result.`,
  argDescriptions: {
    file: fileArgDescription,
    asOf: 'The value to use for caching',
  },
  returnValueDescription: `The direct url of the ${docType('file')}`,
  returnType: inputTypes => maybe('string'),
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const result = await context.backend.getArtifactFileDirectUrl(
        artifact.id,
        path
      );
      return result.directUrl;
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return null;
    }
  },
});

export const opFileMedia = makeFileOp({
  hidden: true,
  name: 'file-media',
  argTypes: fileArgTypes,
  description: `Returns a ${docType('file')} as its Media type`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The ${docType('file')} as its Media type`,
  returnType: ({file}) => {
    if (!isFile(file)) {
      throw new Error('opFileMedia: file must be a File');
    }
    const wbObjectType = file.wbObjectType;
    if (wbObjectType == null) {
      throw new Error('opFileMedia: file must have a wbObjectType');
    }
    return withFileTag(wbObjectType, maybe(file));
  },
  resolver: async (
    {file},
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context
  ) => {
    const {artifact, path} = file;
    if (artifact == null) {
      // TODO: Add support for files stored on run without artifact
      return undefined;
    }
    try {
      // This errors if the sequence has been deleted (or a race case in which
      // the artifact is not created before the history step referencing it comes in)
      const {contents} = await context.backend.getArtifactFileContents(
        artifact.id,
        path
      );
      if (contents == null) {
        return undefined;
      }
      return concreteTaggedValue({file}, JSON.parse(contents));
    } catch (e) {
      console.warn('Error loading artifact', {err: e, artifact, path});
      return concreteTaggedValue({file}, null);
    }
  },
});

export const opFileArtifactVersion = makeFileOp({
  hidden: true,
  name: 'file-artifactVersion',
  argTypes: fileArgTypes,
  description: `Returns the ${docType('artifactVersion')} of the ${docType(
    'file'
  )}`,
  argDescriptions: {
    file: fileArgDescription,
  },
  returnValueDescription: `The ${docType('artifactVersion')} of the ${docType(
    'file'
  )}`,
  returnType: inputTypes => 'artifactVersion',
  resolver: ({file}) => {
    return file.artifact;
  },
});
