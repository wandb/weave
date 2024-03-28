/*
Convention:
* `fn*` functions are node transformations

*/

import stringify from 'json-stable-stringify';

import {
  constFunction,
  constNone,
  constString,
  isObjectType,
  isSimpleTypeShape,
  Node,
  opArtifactAliasAlias,
  opArtifactName,
  opArtifactTypeArtifacts,
  opArtifactTypeName,
  opArtifactVersionAliases,
  opArtifactVersionArtifactSequence,
  opArtifactVersionArtifactType,
  opArtifactVersionCreatedAt,
  opArtifactVersionDescription,
  opArtifactVersionFile,
  opArtifactVersionHash,
  opArtifactVersionId,
  opArtifactVersionIsWeaveObject,
  opArtifactVersions,
  opArtifactVersionVersionId,
  opDict,
  opFileContents,
  opFilter,
  opFlatten,
  opMap,
  opProjectArtifactTypes,
  opRootProject,
  Type,
} from '../../../../../../core';

export const fnAllWeaveObjects = (entity: string, project: string) => {
  const allObjectVersions = allObjectVersionsNode(entity, project);
  const asDictNode = opMap({
    arr: allObjectVersions,
    mapFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return fnObjectVersionToDict(entity, project, row as any);
    }),
  });
  return asDictNode;
};

///

export const typeVersionFromTypeDict = (
  typeDict: Type
): TypeVersionTypeDictType => {
  const typeVersionId = typeIdFromTypeVersion(typeDict);
  const typeName = isSimpleTypeShape(typeDict) ? typeDict : typeDict.type;
  return {
    type_name: typeName,
    type_version: typeVersionId,
    parent_type:
      isObjectType(typeDict) && typeDict._base_type
        ? typeVersionFromTypeDict(typeDict._base_type)
        : undefined,
  };
};

export type ObjectVersionDictType = {
  entity: string;
  project: string;
  artifact_id: string;
  collection_name: string;
  type_version: TypeVersionTypeDictType;
  aliases: string[];
  created_at_ms: number;
  description: string;
  hash: string;
  version_index: number;
};

///

type TypeVersionTypeDictType = {
  type_name: string;
  type_version: string;
  type_dict?: string;
  parent_type?: TypeVersionTypeDictType;
  type_version_json_string?: string;
};

const fnObjectVersionToDict = (
  entity: string,
  project: string,
  objectVersionNode: Node<'artifactVersion'>
) => {
  const sequenceNode = opArtifactVersionArtifactSequence({
    artifactVersion: objectVersionNode,
  });
  return opDict({
    entity: constString(entity),
    project: constString(project),
    artifact_id: opArtifactVersionId({artifactVersion: objectVersionNode}),
    collection_name: opArtifactName({artifact: sequenceNode}),
    type_version: fnObjectVersionTypeVersion(objectVersionNode),
    // type_name: opTypeName({type: opFilesystemArtifactWeaveType({artifact: objectVersionNode} as any)})
    aliases: opArtifactAliasAlias({
      artifactAlias: opArtifactVersionAliases({
        artifactVersion: objectVersionNode,
      }),
    }),
    created_at_ms: opArtifactVersionCreatedAt({
      artifactVersion: objectVersionNode,
    }),
    description: opArtifactVersionDescription({
      artifactVersion: objectVersionNode,
    }),
    hash: fnObjectVersionHash(objectVersionNode),
    version_index: opArtifactVersionVersionId({
      artifactVersion: objectVersionNode,
    }),
  } as any);
};

const fnObjectVersionTypeDictString = (
  objectVersionNode: Node<'artifactVersion'>
) => {
  const fileNode = opFileContents({
    file: opArtifactVersionFile({
      artifactVersion: objectVersionNode,
      path: constString('obj.type.json'),
    }),
  });
  return fileNode;
};

const fnObjectVersionTypeVersion = (
  objectVersionNode: Node<'artifactVersion'>
) => {
  // TODO(tim/weaveflow_improved_nav): This is incorrect for now. We don't have the notion
  // of a type version yet in the weaveflow model. We Are going to make the simplifying assumption
  // that:
  // 1. The name of the artifactType is the same name as the weave type
  // 2. There is only 1 version of each type (totally wrong)
  const artifactTypeNode = opArtifactVersionArtifactType({
    artifactVersion: objectVersionNode,
  }) as Node<'artifactVersion'>;
  return opDict({
    type_name: opArtifactTypeName({artifactType: artifactTypeNode}),
    type_version: constString('unknown'),
    type_version_json_string: fnObjectVersionTypeDictString(objectVersionNode),
    // TODO(tim/weaveflow_improved_nav): This is incorrect for now. We don't have the notion
    parent_type: constNone(),
  } as any);
};

const fnObjectVersionHash = (objectVersionNode: Node<'artifactVersion'>) => {
  return opArtifactVersionHash({artifactVersion: objectVersionNode});
};

const allObjectVersionsNode = (entity: string, project: string) => {
  const projectNode = opRootProject({
    entityName: constString(entity),
    projectName: constString(project),
  });
  const artifactTypesNode = opProjectArtifactTypes({
    project: projectNode,
  });
  const artifactsNode = opFlatten({
    arr: opArtifactTypeArtifacts({
      artifactType: artifactTypesNode,
    }) as any,
  });
  const artifactVersionsNode = opFlatten({
    arr: opArtifactVersions({
      artifact: artifactsNode,
    }) as any,
  });
  const weaveObjectsNode = opFilter({
    arr: artifactVersionsNode,
    filterFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return opArtifactVersionIsWeaveObject({artifactVersion: row});
    }),
  });
  return weaveObjectsNode;
};

const hashString = (s: string) => {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    // tslint:disable-next-line: no-bitwise
    hash = (hash << 5) - hash + s.charCodeAt(i);
    // tslint:disable-next-line: no-bitwise
    hash |= 0; // Convert to 32bit integer
  }
  return '' + hash;
};

const typeIdFromTypeVersion = (typeVersion: any) => {
  return hashString(stringify(typeVersion));
};
