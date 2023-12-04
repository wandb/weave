/*
Convention:
* `fn*` functions are node transformations

*/

import { useMutation} from '@apollo/client';
import { useMemo } from "react"

import { constFunction, constNone, constString, isObjectType, isSimpleTypeShape, Node, opArtifactAliasAlias, opArtifactName, opArtifactTypeArtifacts, opArtifactTypeName, opArtifactVersionAliases, opArtifactVersionArtifactSequence, opArtifactVersionArtifactType, opArtifactVersionCreatedAt, opArtifactVersionDescription, opArtifactVersionFile, opArtifactVersionHash, opArtifactVersionId, opArtifactVersionIsWeaveObject, opArtifactVersions, opArtifactVersionVersionId, opDict, opFileContents, opFilter, opFlatten, opMap, opProjectArtifactTypes, opProjectArtifactVersion, opRootProject, Type } from "../../../../../../core"
import { useNodeValue } from "../../../../../../react"
import { UPDATE_ARTIFACT_DESCRIPTION } from './gql';

export const useAllObjectVersions = (entity: string, project: string): Loadable<ObjectVersionDictType[]> => {
    const allObjectVersions = useMemo(() => allObjectVersionsNode(entity, project), [entity, project])
    const asDictNode = opMap({arr: allObjectVersions, mapFn: constFunction({row: 'artifactVersion'}, ({row}) => {
        return opObjectVersionToDict(row as any)
    })})
    const value = useNodeValue(asDictNode)
    return useMemo(() => {
        if (value.loading) {
            return {loading: true}
        } else {
            const userObjects = removeNonUserObjects(value.result)
            const typeFixedObjects = userObjects.map((obj) => {
                if (obj.type_version.type_version === 'unknown') {
                    return {
                        ...obj,
                        type_version: typeVersionFromTypeDict(JSON.parse((obj.type_version as any).type_version_json_string))}
                }
                return obj
            })
            return {
                loading: false,
                result: typeFixedObjects
            }
        }
    }, [value])
}

export const useUpdateObjectVersionDescription = () => {
    const [updateArtifactDescription] = useMutation(UPDATE_ARTIFACT_DESCRIPTION);
    return (artifactID: string, description: string) => updateArtifactDescription({
        variables: {
            artifactID,
            description,
        }
    })
}

export const useObjectVersionTypeInfo = (entity: string, project: string, object_name: string, object_version_hash: string): Loadable<ObjectVersionDictType> => {
    const objectVersionNode = opProjectArtifactVersion({
        project: opRootProject({
            entityName: constString(entity),
            projectName: constString(project),
        }),
        artifactName: constString(object_name),
        artifactVersionAlias: constString(object_version_hash),
    })
    const value = useNodeValue(opObjectVersionToDict(objectVersionNode as any))
    return value as any
}



export const useAllTypeVersions = (entity: string, project: string): Loadable<{types: TypeVersions, versions:TypeVersionCatalog}> => {
    // This is a super inefficient way to do this... just making it work for now.
    const allObjectVersions = useAllObjectVersions(entity, project)
    const allTypeVersions = useMemo(() => {
        if (allObjectVersions.loading) {
            return {loading: true}
        } else {
            const typeVersionCatalog: TypeVersionCatalog = {}
            const typeVersions: TypeVersions = {}
            const queue = [...allObjectVersions.result.map(objectVersion => objectVersion.type_version)]
            while (queue.length > 0) {
                const type_version = queue.pop()!
                const typeId = typeIdFromTypeVersion(type_version)
                if (!(typeId in typeVersionCatalog)) {
                    typeVersionCatalog[typeId] = {
                        type_name: type_version.type_name,
                        type_version: type_version.type_version,
                        parent_type_id: type_version.parent_type ? typeIdFromTypeVersion(type_version.parent_type) : undefined,
                    }
                    if (type_version.parent_type) {
                        queue.push(type_version.parent_type)
                    }
                }
                if (typeVersions[type_version.type_name] === undefined) {
                    typeVersions[type_version.type_name] = []
                }
                if (!typeVersions[type_version.type_name].includes(typeId)) {
                    typeVersions[type_version.type_name].push(typeId)
                }
            }

            return {
                loading: false,
                result: typeVersionCatalog
            }
        }
    }
    , [allObjectVersions])
    return allTypeVersions as Loadable<TypeVersionCatalog>
}


///

type Loadable<T> = {loading: true, result: undefined | null} | {loading: false, result: T}

type TypeVersionTypeDictType = {
    type_name: string,
    type_version: string,
    type_dict?: string,
    parent_type?: TypeVersionTypeDictType,
}

type TypeVersionCatalog = {
    [typeId: string]: {
        type_name: string,
        type_version: string,
        parent_type_id?: string,
    }
}

type TypeVersions = {
    [typeName: string]: Array<string>;
}


type ObjectVersionDictType = {
    artifact_id: string,
    collection_name: string,
    type_version: TypeVersionTypeDictType
    aliases: string[],
    created_at_ms: number,
    description: string,
    hash: string,
    version_index: number,
}


const nonUserTypes = [
    'OpDef',  'type', 'stream_table'
]
const removeNonUserObjects = (objectVersions: ObjectVersionDictType[]) => {
    return objectVersions.filter(objectVersion => {
        return !nonUserTypes.includes(objectVersion.type_version.type_name)
    })
}

const typeVersionFromTypeDict = (type_dict: Type) => {
    console.log(type_dict)
    const type_version_id = typeIdFromTypeVersion(type_dict)
    const type_name = isSimpleTypeShape(type_dict) ? type_dict : type_dict.type
    return {
        type_name: type_name,
        type_version: type_version_id,
        parent_type: isObjectType(type_dict) && type_dict._base_type ? typeVersionFromTypeDict(type_dict._base_type) : undefined,
    }
}

const opObjectVersionToDict = (objectVersionNode: Node<'artifactVersion'>) => {
    const sequenceNode = opArtifactVersionArtifactSequence({artifactVersion: objectVersionNode})
    return opDict({
        artifact_id: opArtifactVersionId({artifactVersion: objectVersionNode}),
        collection_name: opArtifactName({artifact: sequenceNode}),
        type_version: fnObjectVersionTypeVersion(objectVersionNode),
        // type_name: opTypeName({type: opFilesystemArtifactWeaveType({artifact: objectVersionNode} as any)})
        aliases: opArtifactAliasAlias({artifactAlias:  opArtifactVersionAliases({artifactVersion: objectVersionNode})}),
        created_at_ms: opArtifactVersionCreatedAt({artifactVersion: objectVersionNode}),
        description: opArtifactVersionDescription({artifactVersion: objectVersionNode}),
        hash: fnObjectVersionHash(objectVersionNode),
        version_index :opArtifactVersionVersionId({artifactVersion: objectVersionNode}),
    } as any)
}

const fnObjectVersionTypeDictString = (objectVersionNode: Node<'artifactVersion'>) => {
    const fileNode = opFileContents({file: opArtifactVersionFile({
        artifactVersion: objectVersionNode,
        path: constString('obj.type.json')
    })})
    return fileNode
}

const fnObjectVersionTypeVersion = (objectVersionNode: Node<'artifactVersion'>) => {
    // TODO(tim/weaveflow_improved_nav): This is incorrect for now. We don't have the notion
    // of a type version yet in the weaveflow model. We Are going to make the simplifying assumption
    // that:
    // 1. The name of the artifactType is the same name as the weave type
    // 2. There is only 1 version of each type (totally wrong)
    const artifactTypeNode = opArtifactVersionArtifactType({artifactVersion: objectVersionNode}) as Node<'artifactVersion'>
    return  opDict({
        type_name: opArtifactTypeName({artifactType: artifactTypeNode}),
        type_version: constString("unknown"),
        type_version_json_string: fnObjectVersionTypeDictString(objectVersionNode),
        // TODO(tim/weaveflow_improved_nav): This is incorrect for now. We don't have the notion
        parent_type: constNone()
    } as any)
}

const fnObjectVersionHash = (objectVersionNode: Node<'artifactVersion'>) => {
    return opArtifactVersionHash({artifactVersion: objectVersionNode});
}

const allObjectVersionsNode = (entity: string, project: string) => {
    const projectNode = opRootProject({
        entityName: constString(entity),
        projectName: constString(project),
    })
    const artifactTypesNode = opProjectArtifactTypes({
        project: projectNode,
    })
    const artifactsNode = opFlatten({arr: opArtifactTypeArtifacts({
        artifactType: artifactTypesNode,
    }) as any})
    const artifactVersionsNode = opFlatten({arr: opArtifactVersions({
        artifact: artifactsNode,
    }) as any})
    const weaveObjectsNode = opFilter({arr: artifactVersionsNode, filterFn: constFunction(
        {row: 'artifactVersion'}, ({row}) => {
            return opArtifactVersionIsWeaveObject({artifactVersion: row})
        }
    )})
    return weaveObjectsNode
}



const hashString = (s: string) => {
    let hash = 0;
    for (let i = 0; i < s.length; i++) {
      hash = ((hash << 5) - hash) + s.charCodeAt(i);
      hash |= 0; // Convert to 32bit integer
    }
    return "" + hash;
}

export const typeIdFromTypeVersion = (typeVersion: any) => {
    return hashString(JSON.stringify(typeVersion))
}

