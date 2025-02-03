import _ from 'lodash';

import {useWFHooks} from '../pages/wfReactInterface/context';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';

// Given a list of specifiers like ['obj1:v9', 'obj1:v10', 'obj2:v2']
// return a list of unique object names like ['obj1', 'obj2']
const getUniqueNames = (specifiers: string[]): string[] => {
  const names = specifiers.map(spec => spec.split(':')[0]);
  return [...new Set(names)];
};

// Given a string like v23 return the number 23
// Return null if can't extract a version number
const parseVersionNumber = (versionStr: string): number | null => {
  if (versionStr.startsWith('v')) {
    const num = parseInt(versionStr.slice(1), 10);
    if (!isNaN(num) && num >= 0) {
      return num;
    }
  }
  return null;
};

export const parseSpecifier = (
  specifier: string
): {name: string; version: number | null; versionStr: string} => {
  const parts = specifier.split(':', 2);
  const name = parts[0];
  const versionStr = parts[1] ?? 'latest';
  const version = parseVersionNumber(versionStr);
  return {name, version, versionStr};
};

// Check if we have sequentially increasing version numbers of the same object
export const isSequentialVersions = (specifiers: string[]): boolean => {
  if (specifiers.length < 2) {
    return false;
  }
  const first = parseSpecifier(specifiers[0]);
  if (first.version === null) {
    return false;
  }
  for (let i = 1; i < specifiers.length; i++) {
    const next = parseSpecifier(specifiers[i]);
    if (next.name !== first.name || next.version !== first.version + i) {
      return false;
    }
  }
  return true;
};

// Find object version in array by specifier.
// specifiers can be in the forms:
// name, name:latest, name:v#, name:digest
const findObjectVersion = (
  objectVersions: ObjectVersionSchema[],
  specifier: string
): ObjectVersionSchema | undefined => {
  const {name, versionStr} = parseSpecifier(specifier);
  if (versionStr === 'latest') {
    const correctName = _.filter(objectVersions, {objectId: name});
    return _.maxBy(correctName, 'versionIndex');
  }
  const versionIndex = parseVersionNumber(versionStr);
  if (versionIndex !== null) {
    return objectVersions.find(
      v => v.objectId === name && v.versionIndex === versionIndex
    );
  }
  return objectVersions.find(
    v => v.objectId === name && v.versionHash === versionStr
  );
};

type ObjectVersionsResult = {
  loading: boolean;
  objectVersions: ObjectVersionSchema[];
  lastVersionIndices: Record<string, number>; // Name to number
};

export const useObjectVersions = (
  entity: string,
  project: string,
  objectVersionSpecifiers: string[]
): ObjectVersionsResult => {
  // TODO: Need to introduce a backend query (/objs/read?) to bulk get specific versions of objects
  const {useRootObjectVersions} = useWFHooks();
  const objectIds = getUniqueNames(objectVersionSpecifiers);
  const rootObjectVersions = useRootObjectVersions(
    entity,
    project,
    {
      objectIds,
    },
    undefined, // limit
    // TODO: This is super wasteful - getting all the data for all versions of every object mentioned
    // but hooks on array would be a pain, proper solution is new read API
    false // metadataOnly
  );
  if (rootObjectVersions.loading) {
    return {loading: true, objectVersions: [], lastVersionIndices: {}};
  }

  const result = rootObjectVersions.result ?? [];
  // TODO: Allow ommitting version specifier and handling other cases
  // objname => latest version - 1, latest version
  // obj1, obj2 => latest version for both
  // For now, we require a version specifier for each
  const objectVersions = objectVersionSpecifiers
    .map(spec => findObjectVersion(result, spec))
    .filter((v): v is NonNullable<typeof v> => v !== undefined);
  const lastVersionIndices: Record<string, number> = {};
  for (const obj of result) {
    const current = lastVersionIndices[obj.objectId] ?? -1;
    if (obj.versionIndex > current) {
      lastVersionIndices[obj.objectId] = obj.versionIndex;
    }
  }
  return {loading: false, objectVersions, lastVersionIndices};
};
