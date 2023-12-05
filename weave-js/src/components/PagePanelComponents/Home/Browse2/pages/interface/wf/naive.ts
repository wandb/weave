import {Type} from '../../../../../../../core';
import {Client as WeaveClient} from '../../../../../../../core/client/types';
import { ObjectVersionDictType, fnAllWeaveObjects, typeVersionFromTypeDict } from '../dataModel';
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
      await this.loadOps();
      await this.loadObjects();
      await this.loadCalls();
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

  private async loadOps(): Promise<void> {
    const weaveObjectsNode = fnAllWeaveObjects(this.state.entity, this.state.project);
    const weaveObjectsValue = await this.weaveClient.query(weaveObjectsNode) as ObjectVersionDictType[]
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
    const opVersions = objects.filter(obj => obj.type_version.type_name === 'OpDef');
    const objectVersions = objects.filter(obj => ['OpDef', 'stream_table', 'type'].includes(obj.type_version.type_name));
    
    this.state.opVersionsMap = new Map(opVersions.map(opVersion => {return [opVersion.hash, {
      opName: opVersion.collection_name,
      opVersionHash: opVersion.hash,
      inputTypes: {},
      outputType: null,
      invokes: [],
      description: opVersion.description,
      versionIndex: opVersion.version_index,
      code: undefined,
      createdAt: opVersion.created_at_ms,
    }]}))
    
  }

  private async loadObjects(): Promise<void> {
    // remember to load type/versions within objects as well.
  }

  private async loadCalls(): Promise<void> {}
}

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
          this.state.typeVersionsMap.get(typeVersionId)?.typeName ===
          this.typeName
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
    const objectDict = this.state.opVersionsMap.get(objectName);
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
    const opDict = this.state.opsMap.get(opName);
    if (!opDict) {
      throw new Error(
        `Cannot find type with name: ${opName} in project: ${this.state.project}`
      );
    }
    this.opDict = opDict;
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
  typeName: string;
  typeVersionId: string;
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
    return new WFNaiveType(this.state, this.typeVersionDict.typeName);
  }
  version(): string {
    return this.typeVersionDict.typeVersionId;
  }
  rawWeaveType(): Type {
    throw new Error('Method not implemented.');
  }
  properties(): {[propName: string]: WFTypeVersion} {
    throw new Error('Method not implemented.');
  }
  parentTypeVersion(): WFTypeVersion | null {
    throw new Error('Method not implemented.');
  }
  childTypeVersions(): WFTypeVersion[] {
    throw new Error('Method not implemented.');
  }
  inputsTo(): Array<{argName: string; opVersion: WFOpVersion}> {
    throw new Error('Method not implemented.');
  }
  outputFrom(): WFOpVersion[] {
    throw new Error('Method not implemented.');
  }
  objectVersions(): WFObjectVersion[] {
    throw new Error('Method not implemented.');
  }
}

type WFNaiveObjectVersionDictType = {};
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
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
  object(): WFObject {
    throw new Error('Method not implemented.');
  }
  version(): string {
    throw new Error('Method not implemented.');
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
  type(): WFTypeVersion {
    throw new Error('Method not implemented.');
  }
  inputsTo(): Array<{argName: string; opVersion: WFCall}> {
    throw new Error('Method not implemented.');
  }
  outputFrom(): WFCall[] {
    throw new Error('Method not implemented.');
  }
  description(): string {
    throw new Error('Method not implemented.');
  }
}

type WFNaiveOpVersionDictType = {
  opName: string;
  opVersionHash: string;
  inputTypes: {[argName: string]: unknown};
  outputType: unknown;
  invokes: Array<{
    opName: string;
    opVersionHash: string;
  }>;
  description: string;
  versionIndex: number;
  code?: string;
  createdAt: number;
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
  op(): WFOp {
    throw new Error('Method not implemented.');
  }
  version(): string {
    throw new Error('Method not implemented.');
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
    throw new Error('Method not implemented.');
  }
  description(): string {
    throw new Error('Method not implemented.');
  }
  entity(): string {
    return this.state.entity;
  }
  project(): string {
    return this.state.project;
  }
}

type WFNaiveCallDictType = {};
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
