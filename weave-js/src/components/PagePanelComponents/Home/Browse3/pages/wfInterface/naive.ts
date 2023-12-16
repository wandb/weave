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
  opVersion(name: string, version: string): WFOpVersion | null {
    if (!this.state.opVersionsMap.has(version)) {
      return null;
      // throw new Error(
      //   `Cannot find version: ${version} in project: ${this.state.project}`
      // );
    }
    return new WFNaiveOpVersion(this.state, version);
  }
  opVersions(): WFOpVersion[] {
    return Array.from(this.state.opVersionsMap.keys()).map(opName => {
      return new WFNaiveOpVersion(this.state, opName);
    });
  }
  objectVersion(name: string, version: string): WFObjectVersion | null {
    if (!this.state.objectVersionsMap.has(version)) {
      return null;
      // throw new Error(
      //   `Cannot find version: ${version} in project: ${this.state.project}`
      // );
    }
    return new WFNaiveObjectVersion(this.state, version);
  }
  objectVersions(): WFObjectVersion[] {
    return Array.from(this.state.objectVersionsMap.keys()).map(opName => {
      return new WFNaiveObjectVersion(this.state, opName);
    });
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
    const joinedCalls = joinRunsWithFeedback(
      runsValue ?? [],
      feedbackValue ?? []
    );
    const objects =
      weaveObjectsValue?.map(obj => {
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
      }) ?? [];
    const opVersions = objects.filter(
      obj => obj.type_version.type_name === 'OpDef'
    );
    const objectVersions = objects.filter(
      obj =>
        !['OpDef', 'stream_table', 'type'].includes(obj.type_version.type_name)
    );
    const objectTypeVersions = objectVersions.map(obj => obj.type_version);

    this.state.objectVersionsMap = new Map(
      objectVersions.map(objectVersion => {
        return [
          objectVersion.hash,
          {
            name: objectVersion.collection_name,
            versionHash: objectVersion.hash,
            createdAt: objectVersion.created_at_ms,
            aliases: objectVersion.aliases,
            description: objectVersion.description,
            versionIndex: objectVersion.version_index,
            typeVersionHash: objectVersion.type_version.type_version,
          },
        ];
      })
    );

    this.state.objectsMap = new Map(
      Array.from(this.state.objectVersionsMap.entries()).map(
        ([objectVersionHash, objectVersionDict]) => {
          return [objectVersionDict.name, {}];
        }
      )
    );

    this.state.opVersionsMap = new Map(
      opVersions.map(opVersion => {
        return [
          opVersion.hash,
          {
            name: opVersion.collection_name,
            versionHash: opVersion.hash,
            createdAt: opVersion.created_at_ms,
            aliases: opVersion.aliases,
            description: opVersion.description,
            versionIndex: opVersion.version_index,
            // inputTypes: {},
            // outputType: null,
            invokesOpVersionHashes: [],
            code: undefined,
            inputTypeVersionHashes: [],
            outputTypeVersionHashes: [],
          },
        ];
      })
    );

    this.state.opsMap = new Map(
      Array.from(this.state.opVersionsMap.entries()).map(
        ([opVersionHash, opVersionDict]) => {
          return [opVersionDict.name, {}];
        }
      )
    );

    const typeVersionsDict: {[key: string]: WFNaiveTypeVersionDictType} = {};
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
        parentTypeVersionHash:
          typeVersion.parent_type?.type_version ?? undefined,
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

    this.state.typeVersionsMap = new Map(Object.entries(typeVersionsDict));

    this.state.typesMap = new Map(
      Array.from(this.state.typeVersionsMap.entries()).map(
        ([typeVersionHash, typeVersionDict]) => {
          return [typeVersionDict.name, {}];
        }
      )
    );

    this.state.callsMap = new Map(
      joinedCalls.map(call => {
        const name = call.name;
        const nameParts = uriToParts(name);
        let opVersionHash: string | undefined;
        if (nameParts) {
          const opVersion = this.state.opVersionsMap.get(nameParts.version);
          if (opVersion) {
            opVersionHash = nameParts.version;
          }
        }
        const inputObjectVersionHashes: string[] = [];
        const outputObjectVersionHashes: string[] = [];

        Object.values(call.inputs).forEach((input: any) => {
          if (typeof input === 'string') {
            const inputCallNameParts = uriToParts(input);
            if (inputCallNameParts) {
              const objectVersion = this.state.objectVersionsMap.get(
                inputCallNameParts.version
              );
              if (objectVersion) {
                inputObjectVersionHashes.push(inputCallNameParts.version);
              }
            }
          }
        });

        Object.values(call.output ?? {}).forEach((output: any) => {
          if (typeof output === 'string') {
            const outputCallnameParts = uriToParts(output);
            if (outputCallnameParts) {
              const objectVersion = this.state.objectVersionsMap.get(
                outputCallnameParts.version
              );
              if (objectVersion) {
                outputObjectVersionHashes.push(outputCallnameParts.version);
              }
            }
          }
        });

        return [
          call.span_id,
          {
            callSpan: call,
            opVersionHash,
            inputObjectVersionHashes,
            outputObjectVersionHashes,
          },
        ];
      })
    );

    // Populate invokesOpVersionHashes
    this.opVersions().forEach(opVersion => {
      const selfOpVersion = this.state.opVersionsMap.get(opVersion.version());
      if (!selfOpVersion) {
        return;
      }
      const calls = opVersion.calls();
      if (calls.length === 0) {
        return;
      }
      const exampleCall = calls[0];

      // Populate invokesOpVersionHashes
      const invokesMap: Set<string> = new Set();
      const childCalls = exampleCall.childCalls();
      childCalls.forEach(childCall => {
        const childCallVersion = childCall.opVersion();
        if (!childCallVersion) {
          return;
        }

        invokesMap.add(childCallVersion.version());
      });
      selfOpVersion.invokesOpVersionHashes = Array.from(invokesMap);

      // Populate inputTypeVersionHashes and outputTypeVersionHashes
      const inputTypeVersionMap: Set<string> = new Set();
      const outputTypeVersionMap: Set<string> = new Set();
      const exampleCallDict = this.state.callsMap.get(exampleCall.callID());
      if (!exampleCallDict) {
        return;
      }
      exampleCall.inputs().forEach(input => {
        inputTypeVersionMap.add(input.typeVersion().version());
      });
      exampleCall.output().forEach(output => {
        outputTypeVersionMap.add(output.typeVersion().version());
      });
      selfOpVersion.inputTypeVersionHashes = Array.from(inputTypeVersionMap);
      selfOpVersion.outputTypeVersionHashes = Array.from(outputTypeVersionMap);
    });
  }
}

const uriToParts = (uri: string) => {
  if (uri.startsWith('wandb-artifact:///') && uri.endsWith('/obj')) {
    const inner = uri.slice('wandb-artifact:///'.length, -'/obj'.length);
    const [entity, project, nameAndVersion] = inner.split('/');
    const [name, version] = nameAndVersion.split(':');
    return {entity, project, name, version};
  }
  return null;
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
      .filter(objectVersionDict => objectVersionDict.name === this.objectName)
      .map(
        objectVersionDict =>
          new WFNaiveObjectVersion(this.state, objectVersionDict.versionHash)
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
      .filter(opVersionDict => opVersionDict.name === this.opName)
      .map(
        opVersionDict =>
          new WFNaiveOpVersion(this.state, opVersionDict.versionHash)
      );
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
        return opVersionDict.inputTypeVersionHashes.includes(
          this.typeVersionDict.versionHash
        );
      })
      .map(opVersionDict => {
        return new WFNaiveOpVersion(this.state, opVersionDict.versionHash);
      });
  }
  outputFrom(): WFOpVersion[] {
    return Array.from(this.state.opVersionsMap.values())
      .filter(opVersionDict => {
        return opVersionDict.outputTypeVersionHashes.includes(
          this.typeVersionDict.versionHash
        );
      })
      .map(opVersionDict => {
        return new WFNaiveOpVersion(this.state, opVersionDict.versionHash);
      });
  }
  objectVersions(): WFObjectVersion[] {
    return Array.from(this.state.objectVersionsMap.values())
      .filter(
        objectVersionDict =>
          objectVersionDict.typeVersionHash === this.typeVersionDict.versionHash
      )
      .map(objectVersionDict => {
        return new WFNaiveObjectVersion(
          this.state,
          objectVersionDict.versionHash
        );
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
  // Standard Artifact properties
  name: string;
  versionHash: string;
  description: string;
  versionIndex: number;
  createdAt: number;
  aliases: string[];

  // Op Specific properties
  typeVersionHash: string;

  // Relationships
};
class WFNaiveObjectVersion implements WFObjectVersion {
  private readonly objectVersionDict: WFNaiveObjectVersionDictType;
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly objectVersionId: string
  ) {
    const objectVersionDict = this.state.objectVersionsMap.get(objectVersionId);
    if (!objectVersionDict) {
      throw new Error(
        `Cannot find ObjectVersion with id: ${objectVersionId} in project: ${this.state.project}`
      );
    }
    this.objectVersionDict = objectVersionDict;
  }
  createdAtMs(): number {
    return this.objectVersionDict.createdAt;
  }
  versionIndex(): number {
    return this.objectVersionDict.versionIndex;
  }
  aliases(): string[] {
    return this.objectVersionDict.aliases;
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  object(): WFObject {
    return new WFNaiveObject(this.state, this.objectVersionDict.name);
  }
  version(): string {
    return this.objectVersionDict.versionHash;
  }
  properties(): {[propName: string]: WFObjectVersion} {
    throw new Error('Method not implemented.');
  }
  parentObjectVersion(): {path: string; objectVersion: WFObjectVersion} | null {
    throw new Error('Method not implemented.');
  }
  typeVersion(): WFTypeVersion {
    return new WFNaiveTypeVersion(
      this.state,
      this.objectVersionDict.typeVersionHash
    );
  }
  inputTo(): WFCall[] {
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return callDict.inputObjectVersionHashes?.includes(
          this.objectVersionDict.versionHash
        );
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  outputFrom(): WFCall[] {
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return callDict.outputObjectVersionHashes?.includes(
          this.objectVersionDict.versionHash
        );
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  description(): string {
    return this.objectVersionDict.description;
  }
  refUri(): string {
    return `wandb-artifact:///${this.state.entity}/${this.state.project}/${this.objectVersionDict.name}:${this.objectVersionDict.versionHash}/obj`;
  }
}

type WFNaiveOpVersionDictType = {
  // Standard Artifact properties
  name: string;
  versionHash: string;
  description: string;
  versionIndex: number;
  createdAt: number;
  aliases: string[];

  // Op Specific properties
  inputTypeVersionHashes: string[];
  outputTypeVersionHashes: string[];

  // Relationships
  invokesOpVersionHashes: string[];
};
class WFNaiveOpVersion implements WFOpVersion {
  private readonly opVersionDict: WFNaiveOpVersionDictType;
  constructor(
    private readonly state: WFNaiveProjectState,
    private readonly opVersionHash: string
  ) {
    const opVersionDict = this.state.opVersionsMap.get(opVersionHash);
    if (!opVersionDict) {
      throw new Error(
        `Cannot find OpVersion with id: ${opVersionHash} in project: ${this.state.project}`
      );
    }
    this.opVersionDict = opVersionDict;
  }
  opCategory(): HackyOpCategory | null {
    const opName = this.opVersionDict.name;
    const categories = ['train', 'predict', 'score', 'evaluate', 'tune'];
    for (const category of categories) {
      if (opName.toLocaleLowerCase().includes(category)) {
        return category as HackyOpCategory;
      }
    }
    return null;
  }
  createdAtMs(): number {
    return this.opVersionDict.createdAt;
  }
  versionIndex(): number {
    return this.opVersionDict.versionIndex;
  }
  aliases(): string[] {
    return this.opVersionDict.aliases;
  }
  op(): WFOp {
    return new WFNaiveOp(this.state, this.opVersionDict.name);
  }
  version(): string {
    return this.opVersionDict.versionHash;
  }
  inputTypesVersions(): WFTypeVersion[] {
    return this.opVersionDict.inputTypeVersionHashes.map(typeVersionHash => {
      return new WFNaiveTypeVersion(this.state, typeVersionHash);
    });
  }
  outputTypeVersions(): WFTypeVersion[] {
    return this.opVersionDict.outputTypeVersionHashes.map(typeVersionHash => {
      return new WFNaiveTypeVersion(this.state, typeVersionHash);
    });
  }
  invokes(): WFOpVersion[] {
    return this.opVersionDict.invokesOpVersionHashes.map(opVersionHash => {
      return new WFNaiveOpVersion(this.state, opVersionHash);
    });
  }
  invokedBy(): WFOpVersion[] {
    return Array.from(this.state.opVersionsMap.values())
      .filter(opVersionDict => {
        return opVersionDict.invokesOpVersionHashes.includes(
          this.opVersionDict.versionHash
        );
      })
      .map(opVersionDict => {
        return new WFNaiveOpVersion(this.state, opVersionDict.versionHash);
      });
  }
  calls(): WFCall[] {
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return callDict.opVersionHash === this.opVersionDict.versionHash;
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  description(): string {
    return this.opVersionDict.description;
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  refUri(): string {
    return `wandb-artifact:///${this.state.entity}/${this.state.project}/${this.opVersionDict.name}:${this.opVersionDict.versionHash}/obj`;
  }
}

type WFNaiveCallDictType = {
  callSpan: Call;
  opVersionHash?: string;
  inputObjectVersionHashes: string[];
  outputObjectVersionHashes: string[];
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
    if (!this.callDict.opVersionHash) {
      return null;
    }
    return new WFNaiveOpVersion(this.state, this.callDict.opVersionHash);
  }
  inputs(): WFObjectVersion[] {
    return this.callDict.inputObjectVersionHashes.map(objectVersionHash => {
      return new WFNaiveObjectVersion(this.state, objectVersionHash);
    });
  }
  output(): WFObjectVersion[] {
    return this.callDict.outputObjectVersionHashes.map(objectVersionHash => {
      return new WFNaiveObjectVersion(this.state, objectVersionHash);
    });
  }
  parentCall(): WFCall | null {
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
}
