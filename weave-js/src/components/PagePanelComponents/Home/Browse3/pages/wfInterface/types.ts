import {Type} from '../../../../../../core';
import {Call} from '../../../Browse2/callTree';

export interface WFProject extends ProjectOwned {
  type: (name: string) => WFType | null;
  types: () => WFType[];
  op: (name: string) => WFOp | null;
  ops: () => WFOp[];
  object: (name: string) => WFObject | null;
  objects: () => WFObject[];
  typeVersion: (name: string, version: string) => WFTypeVersion | null;
  typeVersions: () => WFTypeVersion[];
  opVersion: (name: string, version: string) => WFOpVersion | null;
  opVersions: () => WFOpVersion[];
  objectVersion: (name: string, version: string) => WFObjectVersion | null;
  objectVersions: () => WFObjectVersion[];
  call: (callID: string) => WFCall | null;
  calls: () => WFCall[];
  // a bit hacky here:
  traceRoots: (traceID: string) => WFCall[];
  opCategories: () => HackyOpCategory[];
  typeCategories: () => HackyTypeCategory[];
}

interface ProjectOwned {
  entity: () => string;
  project: () => string;
}

interface ArtifactVersionBacked {
  versionIndex: () => number;
  aliases: () => string[];
  description: () => string;
  createdAtMs: () => number;
  refUri: () => string;
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

export type HackyTypeTree = string | {[propName: string]: HackyTypeTree};
export type HackyTypeCategory = 'model' | 'dataset';

export interface WFTypeVersion extends ProjectOwned {
  type: () => WFType;
  version: () => string;
  rawWeaveType: () => Type;
  propertyTypeTree: () => HackyTypeTree;
  // properties: () => {[propName: string]: WFTypeVersion};
  parentTypeVersion: () => WFTypeVersion | null;
  childTypeVersions: () => WFTypeVersion[];
  inputTo: () => WFOpVersion[];
  outputFrom: () => WFOpVersion[];
  objectVersions: () => WFObjectVersion[];
  typeCategory: () => HackyTypeCategory | null; // not technically part of data model since it is derived from the op details
}

export type HackyOpCategory =
  | 'train'
  | 'predict'
  | 'score'
  | 'evaluate'
  | 'tune';

export interface WFOpVersion extends ProjectOwned, ArtifactVersionBacked {
  op: () => WFOp;
  version: () => string;
  inputTypesVersions: () => WFTypeVersion[]; // {[argName: string]: WFTypeVersion};
  outputTypeVersions: () => WFTypeVersion[]; // WFTypeVersion
  invokes: () => WFOpVersion[];
  invokedBy: () => WFOpVersion[];
  calls: () => WFCall[];
  opCategory: () => HackyOpCategory | null; // not technically part of data model since it is derived from the op details
}

export interface WFObjectVersion extends ProjectOwned, ArtifactVersionBacked {
  object: () => WFObject;
  version: () => string;
  properties: () => {[propName: string]: WFObjectVersion};
  parentObjectVersion: () => {
    path: string;
    objectVersion: WFObjectVersion;
  } | null;
  typeVersion: () => WFTypeVersion;
  inputTo: () => WFCall[]; // Array<{argName: string; opVersion: WFCall}>;
  outputFrom: () => WFCall[];
}

export interface WFCall extends ProjectOwned {
  callID: () => string;
  traceID: () => string;
  opVersion: () => WFOpVersion | null;
  inputs: () => WFObjectVersion[]; // {[argName: string]: WFObjectVersion};
  output: () => WFObjectVersion[]; // WFObjectVersion;
  parentCall: () => WFCall | null;
  childCalls: () => WFCall[];
  spanName: () => string; // not technically part of data model since it is derived from the span details
  rawCallSpan: () => Call; // add on
}
