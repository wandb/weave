/*
Convention:
* `fn*` functions are node transformations

*/

import {useMutation} from '@apollo/client';
import {useMemo} from 'react';

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
  opProjectArtifactType,
  opProjectArtifactTypes,
  opProjectArtifactVersion,
  opRootProject,
  Type,
} from '../../../../../../core';
import {useNodeValue} from '../../../../../../react';
import {UPDATE_ARTIFACT_DESCRIPTION} from './gql';

export const useAllObjectVersions = (
  entity: string,
  project: string
): Loadable<ObjectVersionDictType[]> => {
  const allObjectVersions = useMemo(
    () => allObjectVersionsNode(entity, project),
    [entity, project]
  );
  const asDictNode = opMap({
    arr: allObjectVersions,
    mapFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return fnObjectVersionToDict(row as any);
    }),
  });
  const value = useNodeValue(asDictNode);
  return useMemo(() => {
    if (value.loading) {
      return {loading: true};
    } else {
      const userObjects = removeNonUserObjects(value.result);
      const typeFixedObjects = userObjects.map(obj => {
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
      return {
        loading: false,
        result: typeFixedObjects,
      };
    }
  }, [value]);
};

export const useAllOpVersions = (
  entity: string,
  project: string
): Loadable<OpVersionDictType[]> => {
  const allOpVersions = useMemo(
    () => allOpVersionNodes(entity, project),
    [entity, project]
  );
  const asDictNode = opMap({
    arr: allOpVersions,
    mapFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return fnOpVersionToDict(row as any);
    }),
  });
  const value = useNodeValue(asDictNode);
  return useMemo(() => {
    console.log(value);
    return value;
    // if (value.loading) {
    //     return {loading: true}
    // } else {
    //     const userObjects = removeNonUserObjects(value.result)
    //     const typeFixedObjects = userObjects.map((obj) => {
    //         if (obj.type_version.type_version === 'unknown') {
    //             return {
    //                 ...obj,
    //                 type_version: typeVersionFromTypeDict(JSON.parse((obj.type_version as any).type_version_json_string))}
    //         }
    //         return obj
    //     })
    //     return {
    //         loading: false,
    //         result: typeFixedObjects
    //     }
    // }
  }, [value]);
};

export const fnAllWeaveObjects = (
  entity: string,
  project: string
)  => {
  const allObjectVersions = allObjectVersionsNode(entity, project)
  const asDictNode = opMap({
    arr: allObjectVersions,
    mapFn: constFunction({row: 'artifactVersion'}, ({row}) => {
      return fnObjectVersionToDict(row as any);
    }),
  });
  return asDictNode;
}

export const useUpdateObjectVersionDescription = () => {
  const [updateArtifactDescription] = useMutation(UPDATE_ARTIFACT_DESCRIPTION);
  return (artifactID: string, description: string) =>
    updateArtifactDescription({
      variables: {
        artifactID,
        description,
      },
    });
};

export const useObjectVersionTypeInfo = (
  entity: string,
  project: string,
  objectName: string,
  objectVersionHash: string
): Loadable<ObjectVersionDictType> => {
  const objectVersionNode = opProjectArtifactVersion({
    project: opRootProject({
      entityName: constString(entity),
      projectName: constString(project),
    }),
    artifactName: constString(objectName),
    artifactVersionAlias: constString(objectVersionHash),
  });
  const value = useNodeValue(fnObjectVersionToDict(objectVersionNode as any));
  return value as any;
};

export const useAllTypeVersions = (
  entity: string,
  project: string
): Loadable<{types: TypeVersions; versions: TypeVersionCatalog}> => {
  // This is a super inefficient way to do this... just making it work for now.
  // TODO: Get all types from ops as well!
  const allObjectVersions = useAllObjectVersions(entity, project);
  const allTypeVersions = useMemo(() => {
    if (allObjectVersions.loading) {
      return {loading: true};
    } else {
      const typeVersionCatalog: TypeVersionCatalog = {};
      const typeVersions: TypeVersions = {};
      const queue = [
        ...allObjectVersions.result.map(
          objectVersion => objectVersion.type_version
        ),
      ];
      while (queue.length > 0) {
        const typeVersion = queue.pop()!;
        const typeId = typeIdFromTypeVersion(typeVersion);
        if (!(typeId in typeVersionCatalog)) {
          typeVersionCatalog[typeId] = {
            type_name: typeVersion.type_name,
            type_version: typeVersion.type_version,
            parent_type_id: typeVersion.parent_type
              ? typeIdFromTypeVersion(typeVersion.parent_type)
              : undefined,
          };
          if (typeVersion.parent_type) {
            queue.push(typeVersion.parent_type);
          }
        }
        if (typeVersions[typeVersion.type_name] === undefined) {
          typeVersions[typeVersion.type_name] = [];
        }
        if (!typeVersions[typeVersion.type_name].includes(typeId)) {
          typeVersions[typeVersion.type_name].push(typeId);
        }
      }

      return {
        loading: false,
        result: typeVersionCatalog,
      };
    }
  }, [allObjectVersions]);
  return allTypeVersions as Loadable<TypeVersionCatalog>;
};



///

type Loadable<T> =
  | {loading: true; result: undefined | null}
  | {loading: false; result: T};

type TypeVersionTypeDictType = {
  type_name: string;
  type_version: string;
  type_dict?: string;
  parent_type?: TypeVersionTypeDictType;
};

type TypeVersionCatalog = {
  [typeId: string]: {
    type_name: string;
    type_version: string;
    parent_type_id?: string;
  };
};

type TypeVersions = {
  [typeName: string]: string[];
};

export type ObjectVersionDictType = {
  artifact_id: string;
  collection_name: string;
  type_version: TypeVersionTypeDictType;
  aliases: string[];
  created_at_ms: number;
  description: string;
  hash: string;
  version_index: number;
};

type OpVersionDictType = {
  op_name: string;
  op_version: string;
  input_types: {
    [inputName: string]: TypeVersionTypeDictType;
  };
  output_type: TypeVersionTypeDictType;
};

const nonUserTypes = ['OpDef', 'type', 'stream_table'];
const removeNonUserObjects = (objectVersions: ObjectVersionDictType[]) => {
  return objectVersions.filter(objectVersion => {
    return !nonUserTypes.includes(objectVersion.type_version.type_name);
  });
};

export const typeVersionFromTypeDict = (typeDict: Type): TypeVersionTypeDictType => {
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

const fnObjectVersionToDict = (objectVersionNode: Node<'artifactVersion'>) => {
  const sequenceNode = opArtifactVersionArtifactSequence({
    artifactVersion: objectVersionNode,
  });
  return opDict({
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

const fnOpVersionToDict = (opVersionNode: Node<'artifactVersion'>) => {
  const sequenceNode = opArtifactVersionArtifactSequence({
    artifactVersion: opVersionNode,
  });
  return opDict({
    artifact_id: opArtifactVersionId({artifactVersion: opVersionNode}),
    collection_name: opArtifactName({artifact: sequenceNode}),
    // type_version: fnObjectVersionTypeVersion(opVersionNode),
    // type_name: opTypeName({type: opFilesystemArtifactWeaveType({artifact: opVersionNode} as any)})
    // aliases: opArtifactAliasAlias({artifactAlias:  opArtifactVersionAliases({artifactVersion: opVersionNode})}),
    created_at_ms: opArtifactVersionCreatedAt({artifactVersion: opVersionNode}),
    description: opArtifactVersionDescription({artifactVersion: opVersionNode}),
    hash: fnObjectVersionHash(opVersionNode),
    version_index: opArtifactVersionVersionId({artifactVersion: opVersionNode}),
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

const allOpVersionNodes = (entity: string, project: string) => {
  const projectNode = opRootProject({
    entityName: constString(entity),
    projectName: constString(project),
  });
  const artifactTypesNode = opProjectArtifactType({
    project: projectNode,
    artifactTypeName: constString('OpDef'),
  });
  const artifactsNode = opArtifactTypeArtifacts({
    artifactType: artifactTypesNode,
  });
  const artifactVersionsNode = opFlatten({
    arr: opArtifactVersions({
      artifact: artifactsNode,
    }) as any,
  });

  return artifactVersionsNode;
};

const hashString = (s: string) => {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = (hash << 5) - hash + s.charCodeAt(i);
    hash |= 0; // Convert to 32bit integer
  }
  return '' + hash;
};

export const typeIdFromTypeVersion = (typeVersion: any) => {
  return hashString(JSON.stringify(typeVersion));
};
