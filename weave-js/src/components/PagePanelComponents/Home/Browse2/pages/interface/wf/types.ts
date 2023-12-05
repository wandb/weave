import {Type} from '../../../../../../../core';

export interface WFProject extends ProjectOwned {
  type: (name: string) => WFType;
  types: () => WFType[];
  op: (name: string) => WFOp;
  ops: () => WFOp[];
  object: (name: string) => WFObject;
  objects: () => WFObject[];
  typeVersion: (name: string, version: string) => WFTypeVersion;
  typeVersions: () => WFTypeVersion[];
  opVersion: (name: string, version: string) => WFOpVersion;
  opVersions: () => WFOpVersion[];
  objectVersion: (name: string, version: string) => WFObjectVersion;
  objectVersions: () => WFObjectVersion[];
  call: (callID: string) => WFCall;
  calls: () => WFCall[];
}

interface ProjectOwned {
  entity: () => string;
  project: () => string;
}

export interface WFType extends ProjectOwned {
  name: () => string;
  typeVersions: () => WFTypeVersion[];
}

export interface WFOp extends ProjectOwned {
  name: () => string;
  opVersions: () => WFOpVersion[];
}

export interface WFObject extends ProjectOwned {
  name: () => string;
  objectVersions: () => WFObjectVersion[];
}

export interface WFTypeVersion extends ProjectOwned {
  type: () => WFType;
  version: () => string;
  rawWeaveType: () => Type;
  properties: () => {[propName: string]: WFTypeVersion};
  parentTypeVersion: () => WFTypeVersion | null;
  childTypeVersions: () => WFTypeVersion[];
  inputsTo: () => Array<{argName: string; opVersion: WFOpVersion}>;
  outputFrom: () => WFOpVersion[];
  objectVersions: () => WFObjectVersion[];
}

export interface WFOpVersion extends ProjectOwned {
  op: () => WFOp;
  version: () => string;
  code: () => string;
  inputTypes: () => {[argName: string]: WFTypeVersion};
  outputType: () => WFTypeVersion;
  invokes: () => WFOpVersion[];
  invokedBy: () => WFOpVersion[];
  calls: () => WFCall[];
  description: () => string;
}

export interface WFObjectVersion extends ProjectOwned {
  object: () => WFObject;
  version: () => string;
  rawWeaveObject: () => any;
  properties: () => {[propName: string]: WFObjectVersion};
  parentObjectVersion: () => {
    path: string;
    objectVersion: WFObjectVersion;
  } | null;
  type: () => WFTypeVersion;
  inputsTo: () => Array<{argName: string; opVersion: WFCall}>;
  outputFrom: () => WFCall[];
  description: () => string;
}

export interface WFCall extends ProjectOwned {
  callID: () => string;
  opVersion: () => WFOpVersion;
  inputs: () => {[argName: string]: WFObjectVersion};
  output: () => WFObjectVersion;
  parentCall: () => WFCall | null;
  childCalls: () => WFCall[];
}
