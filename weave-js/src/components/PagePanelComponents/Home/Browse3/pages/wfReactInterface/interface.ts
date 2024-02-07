type Loadable<T> = {
    loading: boolean;
    value: T | null;
}

type RefUri = string;

type CallKey = {
    entity: string;
    project: string;
    callId: string;
}
type CallSchema = CallKey & {
    // TODO: Add more fields & FKs
}

export const useGetCall = (key: CallKey): Loadable<CallSchema | null> => {
    throw new Error('Not implemented');
}

type CallFilter = {
    // Filters are ANDed across the fields and ORed within the fields
    opRefs?: string[];
    inputRefs?: string[];
    outputRefs?: string[];
    traceIds?: string[];
    parentIds?: string[];
    callIds?: string[];
    traceRootsOnly?: boolean;
  }
export const useGetCalls = (entity: string, project: string, filter: CallFilter): Loadable<CallSchema[]> => {
    throw new Error('Not implemented');
}

type OpVersionKey = {
    entity: string;
    project: string;
    opId: string;
    version: string;
}

export const refUriToOpVersionKey = (refUri: RefUri): OpVersionKey => {
    const refDict = refStringToRefDict(refUri);
    if (refDict.filePathParts.length !== 1 || refDict.refExtraTuples.length !== 0 || refDict.filePathParts[0] !== 'obj') {
        throw new Error('Invalid refUri: ' + refUri);
    }
    return {
        entity: refDict.entity,
        project: refDict.project,
        opId: refDict.artifactName,
        version: refDict.versionCommitHash,
    }
}
export const opVersionKeyToRefUri = (key: OpVersionKey): RefUri => {
    return `wandb-artifact:///${key.entity}/${key.project}/${key.opId}:${key.version}/obj`;
}


type OpVersionSchema = OpVersionKey  & {
    // TODO: Add more fields & FKs
}

export const useGetOpVersion = (key: OpVersionKey): Loadable<OpVersionSchema | null> => {
    throw new Error('Not implemented');
}

type OpVersionFilter = {
    // Filters are ANDed across the fields and ORed within the fields
    category?: string[];
    opRefs?: string[];
    latestOnly?: boolean;
  }
export const useGetOpVersions = (entity: string, project: string, filter: OpVersionFilter): Loadable<OpVersionSchema[]> => {
    throw new Error('Not implemented');
}

type ObjectVersionKey = {
    entity: string;
    project: string;
    objectId: string;
    versionHash: string;
    path: string;
    refExtra?: string;
}

export const refUriToObjectVersionKey = (refUri: RefUri): ObjectVersionKey => {
    const refDict = refStringToRefDict(refUri);
    return {
        entity: refDict.entity,
        project: refDict.project,
        objectId: refDict.artifactName,
        versionHash: refDict.versionCommitHash,
        path: refDict.filePathParts.join('/'),
        refExtra: refDict.refExtraTuples.map(t => `${t.edgeType}/${t.edgeName}`).join('/')
    }
}

export const objectVersionKeyToRefUri = (key: ObjectVersionKey): RefUri => {
    return `wandb-artifact:///${key.entity}/${key.project}/${key.objectId}:${key.versionHash}/${key.path}${key.refExtra ? '#' + key.refExtra : ''}`;
}

type ObjectVersionSchema = ObjectVersionKey  & {
    // TODO: Add more fields & FKs
}

export const useGetObjectVersion = (key: ObjectVersionKey): Loadable<ObjectVersionSchema | null> => {
    throw new Error('Not implemented');
}

type ObjectVersionFilter = {
    // Filters are ANDed across the fields and ORed within the fields
    category?: string[];
    objectRefs?: string[];
    latestOnly?: boolean;
  }

export const useGetRootObjectVersions = (entity: string, project: string, filter: ObjectVersionFilter): Loadable<ObjectVersionSchema[]> => {
    // Note: Root objects will always have a single path and refExtra will be null
    throw new Error('Not implemented');
}

type WFNaiveRefDict = {
    entity: string;
    project: string;
    artifactName: string;
    versionCommitHash: string;
    filePathParts: string[];
    refExtraTuples: Array<{
      edgeType: string;
      edgeName: string;
    }>;
  };

const refStringToRefDict = (uri: string): WFNaiveRefDict => {
    const scheme = 'wandb-artifact:///';
    if (!uri.startsWith(scheme)) {
      throw new Error('Invalid uri: ' + uri);
    }
    const uriWithoutScheme = uri.slice(scheme.length);
    let uriParts = uriWithoutScheme;
    let refExtraPath = '';
    const refExtraTuples = [];
    if (uriWithoutScheme.includes('#')) {
      [uriParts, refExtraPath] = uriWithoutScheme.split('#');
      const refExtraParts = refExtraPath.split('/');
      if (refExtraParts.length % 2 !== 0) {
        throw new Error('Invalid uri: ' + uri);
      }
      for (let i = 0; i < refExtraParts.length; i += 2) {
        refExtraTuples.push({
          edgeType: refExtraParts[i],
          edgeName: refExtraParts[i + 1],
        });
      }
    }
    const [entity, project, artifactNameAndVersion, filePath] = uriParts.split(
      '/',
      4
    );
    const [artifactName, versionCommitHash] = artifactNameAndVersion.split(':');
    const filePathParts = filePath.split('/');
  
    return {
      entity,
      project,
      artifactName,
      versionCommitHash,
      filePathParts,
      refExtraTuples,
    };
  };
