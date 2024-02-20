import {
  isObjectType,
  isSimpleTypeShape,
  isTypedDictLike,
  Node,
  Type,
  typedDictPropertyTypes,
} from '../../../../../../core';
import {Call} from '../../../Browse2/callTree';
import {
  fnFeedbackNode,
  fnRunsNode,
  joinRunsWithFeedback,
} from '../../../Browse2/callTreeHooks';
import {
  fnAllWeaveObjects,
  ObjectVersionDictType,
  typeVersionFromTypeDict,
} from './query';
import {
  HackyOpCategory,
  HackyTypeCategory,
  HackyTypeTree,
  ReferencedObject,
  WFCall,
  WFObject,
  WFObjectVersion,
  WFOp,
  WFOpVersion,
  WFProject,
  WFType,
  WFTypeVersion,
} from './types';

type WFNaiveProjectState = {
  entity: string;
  project: string;
  typesMap: Map<string, WFNaiveTypeDictType>;
  opsMap: Map<string, WFNaiveOpDictType>;
  objectsMap: Map<string, WFNaiveObjectDictType>;
  typeVersionsMap: Map<string, WFNaiveTypeVersionDictType>;
  opVersionsMap: Map<string, WFNaiveOpVersionDictType>;
  objectVersionsMap: Map<string, WFNaiveObjectVersionDictType>;
  callsMap: Map<string, WFNaiveCallDictType>;
  // Implementation Details
  artifactVersionsMap: Map<string, ObjectVersionDictType>;
};

type WFNaiveArtifactVersionDictType = {
  description: string;
  versionIndex: number;
  createdAt: number;
  aliases: string[];
};

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

export const refStringToRefDict = (uri: string): WFNaiveRefDict => {
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

export const stringIsRef = (maybeRef: string): boolean => {
  try {
    refStringToRefDict(maybeRef);
    return true;
  } catch (e) {
    return false;
  }
};

export const refDictToRefString = (refDict: WFNaiveRefDict): string => {
  const {
    entity,
    project,
    artifactName,
    versionCommitHash,
    filePathParts,
    refExtraTuples,
  } = refDict;
  const refExtraPath = refExtraTuples
    .map(({edgeType, edgeName}) => `${edgeType}/${edgeName}`)
    .join('/');
  return `wandb-artifact:///${entity}/${project}/${artifactName}:${versionCommitHash}/${filePathParts.join(
    '/'
  )}${refExtraPath ? `#${refExtraPath}` : ''}`;
};

const objectVersionDictTypeToWFNaiveRefDict = (
  objectVersionDict: ObjectVersionDictType
): WFNaiveRefDict => {
  return {
    entity: objectVersionDict.entity,
    project: objectVersionDict.project,
    artifactName: objectVersionDict.collection_name,
    versionCommitHash: objectVersionDict.hash,
    filePathParts: ['obj'],
    refExtraTuples: [],
  };
};

const objectVersionDictTypeToArtifactVersionDict = (
  objectVersionDict: ObjectVersionDictType
): WFNaiveArtifactVersionDictType => {
  return {
    description: objectVersionDict.description,
    versionIndex: objectVersionDict.version_index,
    createdAt: objectVersionDict.created_at_ms,
    aliases: objectVersionDict.aliases,
  };
};

export const fnNaiveBootstrapObjects = (
  entity: string,
  project: string
): Node => {
  return fnAllWeaveObjects(entity, project);
};
export const fnNaiveBootstrapRuns = (entity: string, project: string): Node => {
  return fnRunsNode(
    {
      entityName: entity,
      projectName: project,
      streamName: 'stream',
    },
    {}
  );
};
export const fnNaiveBootstrapFeedback = (
  entity: string,
  project: string
): Node => {
  return fnFeedbackNode(entity, project);
};

export class WFNaiveProject implements WFProject {
  private state: WFNaiveProjectState;

  constructor(
    entity: string,
    project: string,
    bootstrapData: {
      objects?: ObjectVersionDictType[];
      runs?: Call[];
      feedback?: any[];
    }
  ) {
    this.state = {
      entity,
      project,
      typesMap: new Map(),
      opsMap: new Map(),
      objectsMap: new Map(),
      typeVersionsMap: new Map(),
      opVersionsMap: new Map(),
      objectVersionsMap: new Map(),
      callsMap: new Map(),
      artifactVersionsMap: new Map(),
    };

    this.bootstrapFromData(
      bootstrapData.objects,
      bootstrapData.runs,
      bootstrapData.feedback
    );
  }

  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }

  type(name: string): WFType | null {
    if (!this.state.typesMap.has(name)) {
      return null;
      // throw new Error(
      //   `Cannot find version with name: ${name} in project: ${this.state.project}`
      // );
    }
    return new WFNaiveType(this.state, name);
  }

  types(): WFType[] {
    return Array.from(this.state.typesMap.keys()).map(typeName => {
      return new WFNaiveType(this.state, typeName);
    });
  }
  op(name: string): WFOp | null {
    if (!this.state.opsMap.has(name)) {
      return null;
      // throw new Error(
      //   `Cannot find version with name: ${name} in project: ${this.state.project}`
      // );
    }
    return new WFNaiveOp(this.state, name);
  }
  ops(): WFOp[] {
    return Array.from(this.state.opsMap.keys()).map(opName => {
      return new WFNaiveOp(this.state, opName);
    });
  }
  object(name: string): WFObject | null {
    if (!this.state.objectsMap.has(name)) {
      return null;
      // throw new Error(
      //   `Cannot find version with name: ${name} in project: ${this.state.project}`
      // );
    }
    return new WFNaiveObject(this.state, name);
  }
  objects(): WFObject[] {
    return Array.from(this.state.objectsMap.keys()).map(opName => {
      return new WFNaiveObject(this.state, opName);
    });
  }
  typeVersion(name: string, version: string): WFTypeVersion | null {
    if (!this.state.typeVersionsMap.has(version)) {
      return null;
      // throw new Error(
      //   `Cannot find version: ${version} in project: ${this.state.project}`
      // );
    }
    return new WFNaiveTypeVersion(this.state, version);
  }
  typeVersions(): WFTypeVersion[] {
    return Array.from(this.state.typeVersionsMap.keys()).map(opName => {
      return new WFNaiveTypeVersion(this.state, opName);
    });
  }
  opVersion(refUriStr: string): WFOpVersion | null {
    // TODO: I think we need to do some more intelligent parsing here
    if (!this.state.opVersionsMap.has(refUriStr)) {
      return null;
      // throw new Error(
      //   `Cannot find version: ${version} in project: ${this.state.project}`
      // );
    }
    return new WFNaiveOpVersion(
      this.state,
      this.state.opVersionsMap.get(refUriStr)!
    );
  }
  opVersions(): WFOpVersion[] {
    return Array.from(this.state.opVersionsMap.values()).map(opVersionDict => {
      return new WFNaiveOpVersion(this.state, opVersionDict);
    });
  }
  objectVersion(refUriStr: string): WFObjectVersion | null {
    return WFNaiveObjectVersion.fromURI(this.state, refUriStr);
  }
  objectVersions(): WFObjectVersion[] {
    return Array.from(this.state.objectVersionsMap.values()).map(
      objectVersionDict => {
        return new WFNaiveObjectVersion(this.state, objectVersionDict);
      }
    );
  }
  call(callID: string): WFCall | null {
    if (!this.state.callsMap.has(callID)) {
      return null;
      // throw new Error(
      //   `Cannot find call with callID: ${callID} in project: ${this.state.project}`
      // );
    }
    return new WFNaiveCall(this.state, callID);
  }
  calls(): WFCall[] {
    return Array.from(this.state.callsMap.keys()).map(opName => {
      return new WFNaiveCall(this.state, opName);
    });
  }

  traceRoots(traceID: string): WFCall[] {
    const rootCalls = Array.from(this.state.callsMap.values()).filter(
      callDict => {
        return callDict.callSpan.trace_id === traceID;
      }
    );
    return rootCalls.map(callDict => {
      return new WFNaiveCall(this.state, callDict.callSpan.span_id);
    });
  }

  opCategories(): HackyOpCategory[] {
    return ['train', 'predict', 'score', 'evaluate', 'tune'];
  }

  typeCategories(): HackyTypeCategory[] {
    return ['model', 'dataset'];
  }

  private bootstrapFromData(
    weaveObjectsValue?: ObjectVersionDictType[],
    runsValue?: Call[],
    feedbackValue?: any[]
  ): void {
    const objects = processWeaveObjects(weaveObjectsValue);
    const {opVersions, objectVersions} = splitWeaveObjects(objects);
    this.state.artifactVersionsMap = bfdObjectsToArtifactVersions(objects);
    this.state.objectVersionsMap = bfdObjectsToObjectVersions(objectVersions);
    this.state.opVersionsMap = bfdOpsToOpVersions(opVersions);
    this.state.callsMap = bfsCallsAndObjectsToCallsMap(
      runsValue ?? [],
      feedbackValue ?? [],
      this.state.opVersionsMap,
      this.state.objectVersionsMap
    );

    // Likely can be removed in future
    this.state.typeVersionsMap =
      bfdObjectVersionsToTypeVersions(objectVersions);
    // Likely can be removed in future
    this.state.objectsMap = bfdObjectVersionsMapToObjectsMap(
      this.state.objectVersionsMap
    );
    // Likely can be removed in future
    this.state.opsMap = bfdOpVersionsMapToOpsMap(this.state.opVersionsMap);
    // Likely can be removed in future
    this.state.typesMap = bfdTypeVersionsToTypeMap(this.state.typeVersionsMap);

    // Infer and populate OpVersion Relationships
    this.opVersions().forEach(opVersion => {
      const selfOpVersion = this.state.opVersionsMap.get(opVersion.refUri());
      if (!selfOpVersion) {
        return;
      }
      const calls = opVersion.calls();
      if (calls.length === 0) {
        return;
      }
      const exampleCall = calls[0];

      // Populate invokesOpVersionRefs
      const invokesMap: Set<string> = new Set();
      const childCalls = exampleCall.childCalls();
      childCalls.forEach(childCall => {
        const childCallVersion = childCall.opVersion();
        if (!childCallVersion) {
          return;
        }

        invokesMap.add(childCallVersion.refUri());
      });
      selfOpVersion.invokesOpVersionRefs = Array.from(invokesMap);

      // Populate inputTypeVersionRefs and outputTypeVersionRefs
      const inputTypeVersionMap: Set<string> = new Set();
      const outputTypeVersionMap: Set<string> = new Set();
      const exampleCallDict = this.state.callsMap.get(exampleCall.callID());
      if (!exampleCallDict) {
        return;
      }
      exampleCall.inputs().forEach(input => {
        const inputType = input.typeVersion();
        if (inputType) {
          inputTypeVersionMap.add(inputType.version());
        }
      });
      exampleCall.output().forEach(output => {
        const outputType = output.typeVersion();
        if (outputType) {
          outputTypeVersionMap.add(outputType.version());
        }
      });
      selfOpVersion.inputTypeVersionRefs = Array.from(inputTypeVersionMap);
      selfOpVersion.outputTypeVersionRefs = Array.from(outputTypeVersionMap);
    });
  }
}

// const uriToParts = (uri: string) => {
//   if (uri.startsWith('wandb-artifact:///') && uri.endsWith('/obj')) {
//     const inner = uri.slice('wandb-artifact:///'.length, -'/obj'.length);
//     const [entity, project, nameAndVersion] = inner.split('/');
//     const [name, version] = nameAndVersion.split(':');
//     return {entity, project, name, version};
//   }
//   return null;
// };

const bfdObjectsToArtifactVersions = (
  objects: ObjectVersionDictType[]
): Map<string, ObjectVersionDictType> => {
  return new Map(
    objects.map(object => {
      return [
        refDictToRefString(objectVersionDictTypeToWFNaiveRefDict(object)),
        object,
      ];
    })
  );
};

const bfdObjectsToObjectVersions = (
  objectVersions: ObjectVersionDictType[]
): Map<string, WFNaiveObjectVersionDictType> => {
  return new Map(
    objectVersions.map(objectVersion => {
      const reference = objectVersionDictTypeToWFNaiveRefDict(objectVersion);
      return [
        refDictToRefString(reference),
        {
          reference,
          artifactVersion:
            objectVersionDictTypeToArtifactVersionDict(objectVersion),
          typeVersionHash: objectVersion.type_version.type_version,
        },
      ];
    })
  );
};

const bfdOpsToOpVersions = (
  opVersions: ObjectVersionDictType[]
): Map<string, WFNaiveOpVersionDictType> => {
  return new Map(
    opVersions.map(opVersion => {
      const reference = objectVersionDictTypeToWFNaiveRefDict(opVersion);
      return [
        refDictToRefString(reference),
        {
          reference,
          artifactVersion:
            objectVersionDictTypeToArtifactVersionDict(opVersion),
          invokesOpVersionRefs: [],
          inputTypeVersionRefs: [],
          outputTypeVersionRefs: [],
        },
      ];
    })
  );
};

const bfdObjectVersionsToTypeVersions = (
  objectVersions: ObjectVersionDictType[]
): Map<string, WFNaiveTypeVersionDictType> => {
  const typeVersionsDict: {[key: string]: WFNaiveTypeVersionDictType} = {};
  const objectTypeVersions = objectVersions.map(obj => obj.type_version);
  const objectTypeVersionsQueue = [...objectTypeVersions];
  while (objectTypeVersionsQueue.length > 0) {
    const typeVersion = objectTypeVersionsQueue.pop();
    if (!typeVersion) {
      continue;
    }
    if (typeVersion.type_version in typeVersionsDict) {
      continue;
    }
    typeVersionsDict[typeVersion.type_version] = {
      name: typeVersion.type_name,
      versionHash: typeVersion.type_version,
      parentTypeVersionHash: typeVersion.parent_type?.type_version ?? undefined,
      rawWeaveType: typeVersion.type_version_json_string
        ? JSON.parse(typeVersion.type_version_json_string)
        : 'unknown',
    };
    if (
      typeVersion.parent_type &&
      !(typeVersion.parent_type.type_version in typeVersionsDict)
    ) {
      objectTypeVersionsQueue.push(typeVersion.parent_type);
    }
  }

  return new Map(Object.entries(typeVersionsDict));
};

const bfdObjectVersionsMapToObjectsMap = (
  objectVersionsMap: Map<string, WFNaiveObjectVersionDictType>
): Map<string, WFNaiveObjectDictType> => {
  return new Map(
    Array.from(objectVersionsMap.entries()).map(
      ([objectVersionHash, objectVersionDict]) => {
        return [objectVersionDict.reference.artifactName, {}];
      }
    )
  );
};

const bfdOpVersionsMapToOpsMap = (
  opVersionsMap: Map<string, WFNaiveOpVersionDictType>
): Map<string, WFNaiveOpDictType> => {
  return new Map(
    Array.from(opVersionsMap.entries()).map(([opVersionRef, opVersionDict]) => {
      return [opVersionDict.reference.artifactName, {}];
    })
  );
};

const bfdTypeVersionsToTypeMap = (
  typeVersionsMap: Map<string, WFNaiveTypeVersionDictType>
): Map<string, WFNaiveTypeDictType> => {
  return new Map(
    Array.from(typeVersionsMap.entries()).map(
      ([typeVersionHash, typeVersionDict]) => {
        return [typeVersionDict.name, {}];
      }
    )
  );
};

const bfsCallsAndObjectsToCallsMap = (
  runsValue: Call[],
  feedbackValue: any[],
  opVersionsMap: Map<string, WFNaiveOpVersionDictType>,
  objectVersionsMap: Map<string, WFNaiveObjectVersionDictType>
): Map<string, WFNaiveCallDictType> => {
  const joinedCalls = joinRunsWithFeedback(runsValue, feedbackValue);
  return new Map(
    joinedCalls.map(call => {
      const name = call.name;
      let opVersionRef: string | undefined;
      if (stringIsRef(name)) {
        opVersionRef = name;
      }
      const inputObjectVersionRefs: string[] = [];
      const outputObjectVersionRefs: string[] = [];

      Object.values(call.inputs).forEach((input: any) => {
        if (typeof input === 'string') {
          if (stringIsRef(input)) {
            inputObjectVersionRefs.push(input);
          }
        }
      });

      Object.values(call.output ?? {}).forEach((output: any) => {
        if (typeof output === 'string') {
          if (stringIsRef(output)) {
            outputObjectVersionRefs.push(output);
          }
        }
      });

      return [
        call.span_id,
        {
          callSpan: call,
          opVersionRef,
          inputObjectVersionRefs,
          outputObjectVersionRefs,
        },
      ];
    })
  );
};

const processWeaveObjects = (
  weaveObjectsValue?: ObjectVersionDictType[]
): ObjectVersionDictType[] => {
  return (
    weaveObjectsValue
      ?.map(obj => {
        if (
          obj.type_version.type_version === 'unknown' &&
          obj.type_version.type_version_json_string
        ) {
          return {
            ...obj,
            type_version: {
              ...typeVersionFromTypeDict(
                JSON.parse(obj.type_version.type_version_json_string)
              ),
              type_version_json_string:
                obj.type_version.type_version_json_string,
            },
          };
        }
        return obj;
      })
      .filter(
        obj => !['stream_table', 'type'].includes(obj.type_version.type_name)
      ) ?? []
  );
};

const splitWeaveObjects = (
  objects: ObjectVersionDictType[]
): {
  opVersions: ObjectVersionDictType[];
  objectVersions: ObjectVersionDictType[];
} => {
  return {
    opVersions: objects.filter(obj => obj.type_version.type_name === 'OpDef'),
    objectVersions: objects.filter(
      obj => obj.type_version.type_name !== 'OpDef'
    ),
  };
};

type WFNaiveTypeDictType = {};

class WFNaiveType implements WFType {
  private readonly typeDict: WFNaiveTypeDictType;
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly typeName: string
  ) {
    const typeDict = this.state.typesMap.get(typeName);
    if (!typeDict) {
      throw new Error(
        `Cannot find type with name: ${typeName} in project: ${this.state.project}`
      );
    }
    this.typeDict = typeDict;
  }
  name(): string {
    return this.typeName;
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  typeVersions(): WFTypeVersion[] {
    return Array.from(this.state.typeVersionsMap.keys())
      .filter(
        typeVersionId =>
          this.state.typeVersionsMap.get(typeVersionId)?.name === this.typeName
      )
      .map(typeVersionId => {
        return new WFNaiveTypeVersion(this.state, typeVersionId);
      });
  }
}

type WFNaiveObjectDictType = {};

class WFNaiveObject implements WFObject {
  private readonly objectDict: WFNaiveObjectDictType;
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly objectName: string
  ) {
    const objectDict = this.state.objectsMap.get(objectName);
    if (!objectDict) {
      throw new Error(
        `Cannot find type with name: ${objectName} in project: ${this.state.project}`
      );
    }
    this.objectDict = objectDict;
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  name(): string {
    return this.objectName;
  }
  objectVersions(): WFObjectVersion[] {
    return Array.from(this.state.objectVersionsMap.values())
      .filter(
        objectVersionDict =>
          objectVersionDict.reference.artifactName === this.objectName
      )
      .map(
        objectVersionDict =>
          new WFNaiveObjectVersion(this.state, objectVersionDict)
      );
  }
}

type WFNaiveOpDictType = {};

class WFNaiveOp implements WFOp {
  private readonly opDict: WFNaiveOpDictType;
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly opName: string
  ) {
    const opDictInternal = this.state.opsMap.get(opName);
    if (!opDictInternal) {
      throw new Error(
        `Cannot find type with name: ${opName} in project: ${this.state.project}`
      );
    }
    this.opDict = opDictInternal;
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  name(): string {
    return this.opName;
  }
  opVersions(): WFOpVersion[] {
    return Array.from(this.state.opVersionsMap.values())
      .filter(
        opVersionDict => opVersionDict.reference.artifactName === this.opName
      )
      .map(opVersionDict => new WFNaiveOpVersion(this.state, opVersionDict));
  }
}

type WFNaiveTypeVersionDictType = {
  name: string;
  versionHash: string;
  rawWeaveType: Type;
  parentTypeVersionHash?: string;
};

class WFNaiveTypeVersion implements WFTypeVersion {
  private readonly typeVersionDict: WFNaiveTypeVersionDictType;
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly typeVersionId: string
  ) {
    const typeVersionDict = this.state.typeVersionsMap.get(typeVersionId);
    if (!typeVersionDict) {
      throw new Error(
        `Cannot find typeVersion with id: ${typeVersionId} in project: ${this.state.project}`
      );
    }
    this.typeVersionDict = typeVersionDict;
  }
  typeCategory(): HackyTypeCategory | null {
    const opName = this.typeVersionDict.name;
    const categories = ['model', 'dataset'];
    for (const category of categories) {
      if (opName.toLocaleLowerCase().includes(category)) {
        return category as HackyTypeCategory;
      }
    }
    return null;
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  type(): WFType {
    return new WFNaiveType(this.state, this.typeVersionDict.name);
  }
  version(): string {
    return this.typeVersionDict.versionHash;
  }
  rawWeaveType(): Type {
    return this.typeVersionDict.rawWeaveType;
  }
  propertyTypeTree(): HackyTypeTree {
    return typeToTypeTree(this.typeVersionDict.rawWeaveType);
  }
  parentTypeVersion(): WFTypeVersion | null {
    if (!this.typeVersionDict.parentTypeVersionHash) {
      return null;
    }
    return new WFNaiveTypeVersion(
      this.state,
      this.typeVersionDict.parentTypeVersionHash
    );
  }
  childTypeVersions(): WFTypeVersion[] {
    return Array.from(this.state.typeVersionsMap.values())
      .filter(
        typeVersionDict =>
          typeVersionDict.parentTypeVersionHash ===
          this.typeVersionDict.versionHash
      )
      .map(typeVersionDict => {
        return new WFNaiveTypeVersion(this.state, typeVersionDict.versionHash);
      });
  }
  inputTo(): WFOpVersion[] {
    return Array.from(this.state.opVersionsMap.values())
      .filter(opVersionDict => {
        return opVersionDict.inputTypeVersionRefs.includes(
          this.typeVersionDict.versionHash
        );
      })
      .map(opVersionDict => {
        return new WFNaiveOpVersion(this.state, opVersionDict);
      });
  }
  outputFrom(): WFOpVersion[] {
    return Array.from(this.state.opVersionsMap.values())
      .filter(opVersionDict => {
        return opVersionDict.outputTypeVersionRefs.includes(
          this.typeVersionDict.versionHash
        );
      })
      .map(opVersionDict => {
        return new WFNaiveOpVersion(this.state, opVersionDict);
      });
  }
  objectVersions(): WFObjectVersion[] {
    return Array.from(this.state.objectVersionsMap.values())
      .filter(
        objectVersionDict =>
          objectVersionDict.typeVersionHash === this.typeVersionDict.versionHash
      )
      .map(objectVersionDict => {
        return new WFNaiveObjectVersion(this.state, objectVersionDict);
      });
  }
}

const typeToTypeTree = (type: Type): HackyTypeTree => {
  if (isSimpleTypeShape(type)) {
    return type;
  } else if (isTypedDictLike(type)) {
    const result: {[propName: string]: HackyTypeTree} = {};
    const propTypes = typedDictPropertyTypes(type);
    for (const [key, value] of Object.entries(propTypes)) {
      result[key] = typeToTypeTree(value);
    }
    return result;
  } else if (isObjectType(type)) {
    const result: {[propName: string]: HackyTypeTree} = {};
    for (const [key, value] of Object.entries(type)) {
      result[key] = typeToTypeTree(value);
    }
    return result;
  }
  return type.type;
};

type WFNaiveObjectVersionDictType = {
  reference: WFNaiveRefDict;
  artifactVersion: WFNaiveArtifactVersionDictType;

  typeVersionHash?: string;
};

class WFNaiveReferencedObject implements ReferencedObject {
  constructor(
    private readonly reference: WFNaiveRefDict,
    private readonly artifactVersion: WFNaiveArtifactVersionDictType
  ) {}
  // TODO: I don't think this should be exposed
  entity(): string {
    return this.reference.entity;
  }
  project(): string {
    return this.reference.project;
  }
  name(): string {
    return this.reference.artifactName;
  }
  commitHash(): string {
    return this.reference.versionCommitHash;
  }
  filePath(): string {
    return this.reference.filePathParts.join('/');
  }
  refExtraPath(): null | string {
    if (this.reference.refExtraTuples.length === 0) {
      return null;
    }
    return this.reference.refExtraTuples
      .map(({edgeType, edgeName}) => `${edgeType}/${edgeName}`)
      .join('/');
  }
  parentObject(): ReferencedObject {
    throw new Error('Method not implemented.');
  }
  childObject(
    refExtraEdgeType: string,
    refExtraEdgeName: string
  ): ReferencedObject {
    throw new Error('Method not implemented.');
  }
  refUri(): string {
    return refDictToRefString(this.reference);
  }
  versionIndex(): number {
    return this.artifactVersion.versionIndex;
  }
  aliases(): string[] {
    return this.artifactVersion.aliases;
  }
}

class WFNaiveObjectVersion
  extends WFNaiveReferencedObject
  implements WFObjectVersion
{
  static fromURI = (
    state: WFNaiveProjectState,
    objectRefUri: string
  ): WFNaiveObjectVersion => {
    // In the case that we are dealing with a refExtra, the objectVersionMap will
    // not contain that (it would be way too expensive)
    const refDict = refStringToRefDict(objectRefUri);
    const refExtraTuples = refDict.refExtraTuples;
    const filePathParts = refDict.filePathParts;
    const objBasedUri = refDictToRefString({
      ...refDict,
      filePathParts: ['obj'],
      refExtraTuples: [],
    });

    let objectVersionDict = state.objectVersionsMap.get(objBasedUri);
    if (!objectVersionDict) {
      throw new Error(
        `Cannot find ObjectVersion with id: ${objectRefUri} in project: ${state.project}`
      );
    }
    if (refExtraTuples.length > 0) {
      objectVersionDict = {
        ...objectVersionDict,
        reference: {
          ...objectVersionDict.reference,
          filePathParts,
          refExtraTuples,
        },
        typeVersionHash: undefined,
      };
    }
    return new WFNaiveObjectVersion(state, objectVersionDict);
  };
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly objectVersionDict: WFNaiveObjectVersionDictType
  ) {
    super(objectVersionDict.reference, objectVersionDict.artifactVersion);
  }
  createdAtMs(): number {
    return this.objectVersionDict.artifactVersion.createdAt;
  }
  versionIndex(): number {
    return this.objectVersionDict.artifactVersion.versionIndex;
  }
  aliases(): string[] {
    return this.objectVersionDict.artifactVersion.aliases;
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  object(): WFObject {
    return new WFNaiveObject(
      this.state,
      this.objectVersionDict.reference.artifactName
    );
  }
  version(): string {
    return this.objectVersionDict.reference.versionCommitHash;
  }
  properties(): {[propName: string]: WFObjectVersion} {
    throw new Error('Method not implemented.');
  }
  parentObjectVersion(): {path: string; objectVersion: WFObjectVersion} | null {
    throw new Error('Method not implemented.');
  }
  typeVersion(): null | WFTypeVersion {
    if (!this.objectVersionDict.typeVersionHash) {
      return null;
    }
    return new WFNaiveTypeVersion(
      this.state,
      this.objectVersionDict.typeVersionHash
    );
  }
  inputTo(): WFCall[] {
    const myRef = refDictToRefString(this.objectVersionDict.reference);
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return callDict.inputObjectVersionRefs?.includes(myRef);
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  outputFrom(): WFCall[] {
    const myRef = refDictToRefString(this.objectVersionDict.reference);
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return callDict.outputObjectVersionRefs?.includes(myRef);
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  description(): string {
    return this.objectVersionDict.artifactVersion.description;
  }
}

type WFNaiveOpVersionDictType = {
  // Standard Artifact properties
  reference: WFNaiveRefDict;
  artifactVersion: WFNaiveArtifactVersionDictType;

  // Op Specific properties
  inputTypeVersionRefs: string[];
  outputTypeVersionRefs: string[];

  // Relationships
  invokesOpVersionRefs: string[];
};
class WFNaiveOpVersion extends WFNaiveReferencedObject implements WFOpVersion {
  static fromURI = (
    state: WFNaiveProjectState,
    opRefUri: string
  ): WFNaiveOpVersion => {
    // For now this works for now since there is only a single op stored in an
    // artifact. If we ever store most stuff in op artifacts, then we might need
    // to extend this to be more like the ObjectVersion.fromURI
    const opVersionDict = state.opVersionsMap.get(opRefUri);
    if (!opVersionDict) {
      throw new Error(
        `Cannot find OpVersion with id: ${opRefUri} in project: ${state.project}`
      );
    }
    return new WFNaiveOpVersion(state, opVersionDict);
  };
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly opVersionDict: WFNaiveOpVersionDictType
  ) {
    super(opVersionDict.reference, opVersionDict.artifactVersion);
  }
  opCategory(): HackyOpCategory | null {
    const opNames = this.opVersionDict.reference.artifactName.split('-');
    const opName = opNames[opNames.length - 1];
    const categories = ['train', 'predict', 'score', 'evaluate', 'tune'];
    for (const category of categories) {
      if (opName.toLocaleLowerCase().includes(category)) {
        return category as HackyOpCategory;
      }
    }
    return null;
  }
  createdAtMs(): number {
    return this.opVersionDict.artifactVersion.createdAt;
  }
  versionIndex(): number {
    return this.opVersionDict.artifactVersion.versionIndex;
  }
  aliases(): string[] {
    return this.opVersionDict.artifactVersion.aliases;
  }
  op(): WFOp {
    return new WFNaiveOp(this.state, this.opVersionDict.reference.artifactName);
  }
  version(): string {
    return this.opVersionDict.reference.versionCommitHash;
  }
  inputTypesVersions(): WFTypeVersion[] {
    return this.opVersionDict.inputTypeVersionRefs.map(typeVersionHash => {
      return new WFNaiveTypeVersion(this.state, typeVersionHash);
    });
  }
  outputTypeVersions(): WFTypeVersion[] {
    return this.opVersionDict.outputTypeVersionRefs.map(typeVersionHash => {
      return new WFNaiveTypeVersion(this.state, typeVersionHash);
    });
  }
  invokes(): WFOpVersion[] {
    return this.opVersionDict.invokesOpVersionRefs.map(opVersionRef => {
      return WFNaiveOpVersion.fromURI(this.state, opVersionRef);
    });
  }
  invokedBy(): WFOpVersion[] {
    const myRef = refDictToRefString(this.opVersionDict.reference);
    return Array.from(this.state.opVersionsMap.values())
      .filter(opVersionDict => {
        return opVersionDict.invokesOpVersionRefs.includes(myRef);
      })
      .map(opVersionDict => {
        return new WFNaiveOpVersion(this.state, opVersionDict);
      });
  }
  calls(): WFCall[] {
    const myRef = refDictToRefString(this.opVersionDict.reference);
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return callDict.opVersionRef === myRef;
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  description(): string {
    return this.opVersionDict.artifactVersion.description;
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
}

type WFNaiveCallDictType = {
  callSpan: Call;
  opVersionRef?: string;
  inputObjectVersionRefs: string[];
  outputObjectVersionRefs: string[];
};
class WFNaiveCall implements WFCall {
  private readonly callDict: WFNaiveCallDictType;
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly callId: string
  ) {
    const callDict = this.state.callsMap.get(callId);
    if (!callDict) {
      throw new Error(
        `Cannot find call with id: ${callId} in project: ${this.state.project}`
      );
    }
    this.callDict = callDict;
  }
  traceID(): string {
    return this.callDict.callSpan.trace_id;
  }
  callID(): string {
    return this.callDict.callSpan.span_id;
  }
  opVersion(): WFOpVersion | null {
    if (!this.callDict.opVersionRef) {
      return null;
    }
    return WFNaiveOpVersion.fromURI(this.state, this.callDict.opVersionRef);
  }
  inputs(): WFObjectVersion[] {
    return this.callDict.inputObjectVersionRefs.map(objectVersionRef => {
      return WFNaiveObjectVersion.fromURI(this.state, objectVersionRef);
    });
  }
  output(): WFObjectVersion[] {
    return this.callDict.outputObjectVersionRefs.map(objectVersionRef => {
      return WFNaiveObjectVersion.fromURI(this.state, objectVersionRef);
    });
  }
  parentCall(): WFCall | null {
    if (!this.callDict.callSpan.parent_id) {
      return null;
    }
    const parentCall = this.state.callsMap.get(
      this.callDict.callSpan.parent_id
    );
    if (!parentCall) {
      return null;
    }
    return new WFNaiveCall(this.state, parentCall.callSpan.span_id);
  }
  childCalls(): WFCall[] {
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return callDict.callSpan.parent_id === this.callDict.callSpan.span_id;
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  spanName(): string {
    return this.opVersion()?.op().name() ?? this.callDict.callSpan.name;
  }
  rawCallSpan(): Call {
    return this.callDict.callSpan;
  }
}
