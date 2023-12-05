import {opDict, Type} from '../../../../../../../core';
import {Client as WeaveClient} from '../../../../../../../core/client/types';
import {Call} from '../../../callTree';
import {
  fnFeedbackNode,
  fnRunsNode,
  joinRunsWithFeedback,
} from '../../../callTreeHooks';
import {
  fnAllWeaveObjects,
  ObjectVersionDictType,
  typeVersionFromTypeDict,
} from '../dataModel';
import {
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

export class WFNaiveProject implements WFProject {
  private initialized: boolean = false;
  private loading: boolean = false;
  private state: WFNaiveProjectState;

  constructor(
    entity: string,
    project: string,
    private readonly weaveClient: WeaveClient
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
  }

  async init(): Promise<void> {
    if (!this.initialized && !this.loading) {
      this.loading = true;
      await this.loadAll();
      this.loading = false;
      this.initialized = true;
    }
    return Promise.resolve();
  }

  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }

  type(name: string): WFType {
    if (!this.state.typesMap.has(name)) {
      throw new Error(
        `Cannot find version with name: ${name} in project: ${this.state.project}`
      );
    }
    return new WFNaiveType(this.state, name);
  }

  types(): WFType[] {
    return Array.from(this.state.typesMap.keys()).map(typeName => {
      return new WFNaiveType(this.state, typeName);
    });
  }
  op(name: string): WFOp {
    if (!this.state.opsMap.has(name)) {
      throw new Error(
        `Cannot find version with name: ${name} in project: ${this.state.project}`
      );
    }
    return new WFNaiveOp(this.state, name);
  }
  ops(): WFOp[] {
    return Array.from(this.state.opsMap.keys()).map(opName => {
      return new WFNaiveOp(this.state, opName);
    });
  }
  object(name: string): WFObject {
    if (!this.state.objectsMap.has(name)) {
      throw new Error(
        `Cannot find version with name: ${name} in project: ${this.state.project}`
      );
    }
    return new WFNaiveObject(this.state, name);
  }
  objects(): WFObject[] {
    return Array.from(this.state.objectsMap.keys()).map(opName => {
      return new WFNaiveObject(this.state, opName);
    });
  }
  typeVersion(name: string, version: string): WFTypeVersion {
    if (!this.state.typeVersionsMap.has(name)) {
      throw new Error(
        `Cannot find version with name: ${name} in project: ${this.state.project}`
      );
    }
    return new WFNaiveTypeVersion(this.state, name);
  }
  typeVersions(): WFTypeVersion[] {
    return Array.from(this.state.typeVersionsMap.keys()).map(opName => {
      return new WFNaiveTypeVersion(this.state, opName);
    });
  }
  opVersion(name: string, version: string): WFOpVersion {
    if (!this.state.opVersionsMap.has(name)) {
      throw new Error(
        `Cannot find version with name: ${name} in project: ${this.state.project}`
      );
    }
    return new WFNaiveOpVersion(this.state, name);
  }
  opVersions(): WFOpVersion[] {
    return Array.from(this.state.opVersionsMap.keys()).map(opName => {
      return new WFNaiveOpVersion(this.state, opName);
    });
  }
  objectVersion(name: string, version: string): WFObjectVersion {
    if (!this.state.objectVersionsMap.has(name)) {
      throw new Error(
        `Cannot find version with name: ${name} in project: ${this.state.project}`
      );
    }
    return new WFNaiveObjectVersion(this.state, name);
  }
  objectVersions(): WFObjectVersion[] {
    return Array.from(this.state.objectVersionsMap.keys()).map(opName => {
      return new WFNaiveObjectVersion(this.state, opName);
    });
  }
  call(callID: string): any {
    if (!this.state.callsMap.has(callID)) {
      throw new Error(
        `Cannot find call with callID: ${callID} in project: ${this.state.project}`
      );
    }
    return new WFNaiveCall(this.state, callID);
  }
  calls(): WFCall[] {
    return Array.from(this.state.callsMap.keys()).map(opName => {
      return new WFNaiveCall(this.state, opName);
    });
  }

  private async loadAll(): Promise<void> {
    const weaveObjectsNode = fnAllWeaveObjects(
      this.state.entity,
      this.state.project
    );
    const runsNode = fnRunsNode(
      {
        entityName: this.state.entity,
        projectName: this.state.project,
        streamName: 'stream',
      },
      {}
    );
    const feedbackNode = fnFeedbackNode(this.state.entity, this.state.project);
    const {
      weaveObjectsNode: weaveObjectsValue,
      runsNode: runsValue,
      feedbackNode: feedbackValue,
    } = (await this.weaveClient.query(
      opDict({weaveObjectsNode, runsNode, feedbackNode} as any)
    )) as {
      weaveObjectsNode: ObjectVersionDictType[];
      runsNode: Call[];
      feedbackNode: any[];
    };
    const joinedCalls = joinRunsWithFeedback(runsValue, feedbackValue ?? []);
    const objects = weaveObjectsValue.map(obj => {
      if (obj.type_version.type_version === 'unknown') {
        return {
          ...obj,
          type_version: typeVersionFromTypeDict(
            JSON.parse((obj.type_version as any).type_version_json_string)
          ),
        };
      }
      return obj;
    });
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
            inputTypes: {},
            outputType: null,
            invokes: [],
            code: undefined,
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
        // const inputKeys = Object.keys(call.inputs)
        // inputKeys
        // let refNdx = 0
        // while (('_ref' + refNdx) in call.inputs && call.inputs[('_ref' + refNdx)]) {
        //   const uri = call.inputs[('_ref' + refNdx)]
        //   const uriParts = uriToParts(uri)
        //   if (uriParts) {
        //     const objectVersion = this.state.objectVersionsMap.get(uriParts.version)
        //     if (objectVersion) {
        //       call.inputs[('_ref' + refNdx)] = objectVersion
        //     }
        //   }
        // }
        return [
          call.span_id,
          {
            callSpan: call,
          },
        ];
      })
    );
  }
}

// const uriToParts = (uri: string) => {
//   if (uri.startsWith('wandb-artifact:///') && uri.endsWith('/obj')) {
//     const inner = uri.slice('wandb-artifact:///'.length, -'/obj'.length);
//     const [entity, project, collection, nameAndVersion] = inner.split('/');
//     const [name, version] = nameAndVersion.split(':');
//     return {entity, project, collection, name, version};
//   }
//   return null
// }

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
    return Object.keys(this.state.typeVersionsMap)
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
    throw new Error('Method not implemented.');
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
    throw new Error('Method not implemented.');
  }
}

type WFNaiveTypeVersionDictType = {
  name: string;
  versionHash: string;
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
    throw new Error('Method not implemented.');
  }
  properties(): {[propName: string]: WFTypeVersion} {
    throw new Error('Method not implemented.');
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
  inputTo(): Array<{argName: string; opVersion: WFOpVersion}> {
    throw new Error('Method not implemented.');
  }
  outputFrom(): WFOpVersion[] {
    throw new Error('Method not implemented.');
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
  rawWeaveObject(): any {
    throw new Error('Method not implemented.');
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
    // Array<{argName: string; opVersion: WFCall}> {
    const targetUri = `wandb-artifact:///${this.state.entity}/${this.state.project}/${this.objectVersionDict.name}:${this.objectVersionDict.versionHash}/obj`;
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return Object.values(callDict.callSpan.inputs).some((input: any) => {
          return input === targetUri;
        });
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  outputFrom(): WFCall[] {
    const targetUri = `wandb-artifact:///${this.state.entity}/${this.state.project}/${this.objectVersionDict.name}:${this.objectVersionDict.versionHash}/obj`;
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        return Object.values(callDict.callSpan.output ?? {}).some(
          (input: any) => {
            return input === targetUri;
          }
        );
      })
      .map(callDict => {
        return new WFNaiveCall(this.state, callDict.callSpan.span_id);
      });
  }
  description(): string {
    return this.objectVersionDict.description;
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
  code?: string;
  inputTypes: {[argName: string]: unknown};
  outputType: unknown;

  // Relationships
  invokes: Array<{
    opName: string;
    opVersionHash: string;
  }>;
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
  code(): string {
    throw new Error('Method not implemented.');
  }
  inputTypes(): {[argName: string]: WFTypeVersion} {
    throw new Error('Method not implemented.');
  }
  outputType(): WFTypeVersion {
    throw new Error('Method not implemented.');
  }
  invokes(): WFOpVersion[] {
    throw new Error('Method not implemented.');
  }
  invokedBy(): WFOpVersion[] {
    throw new Error('Method not implemented.');
  }
  calls(): WFCall[] {
    return Array.from(this.state.callsMap.values())
      .filter(callDict => {
        if (!callDict.callSpan.name.startsWith('wandb-artifact:///')) {
          return false;
        }
        const version = callDict.callSpan.name.split(':')[2].split('/')[0];
        return version === this.opVersionDict.versionHash;
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
}

type WFNaiveCallDictType = {
  callSpan: Call;
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
  callID(): string {
    throw new Error('Method not implemented.');
  }
  opVersion(): WFOpVersion {
    throw new Error('Method not implemented.');
  }
  inputs(): {[argName: string]: WFObjectVersion} {
    throw new Error('Method not implemented.');
  }
  output(): WFObjectVersion {
    throw new Error('Method not implemented.');
  }
  parentCall(): WFCall | null {
    throw new Error('Method not implemented.');
  }
  childCalls(): WFCall[] {
    throw new Error('Method not implemented.');
  }
  entity(): string {
    throw new Error('Method not implemented.');
  }
  project(): string {
    throw new Error('Method not implemented.');
  }
}
