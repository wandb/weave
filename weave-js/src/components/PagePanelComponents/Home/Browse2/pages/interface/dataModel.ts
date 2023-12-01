/*
Convention:
* `fn*` functions are node transformations

*/

import { useMutation} from '@apollo/client';
import { useMemo } from "react"

import { constFunction, constString, Node, opArtifactAliasAlias, opArtifactName, opArtifactTypeArtifacts, opArtifactTypeName, opArtifactVersionAliases, opArtifactVersionArtifactSequence, opArtifactVersionArtifactType, opArtifactVersionCreatedAt, opArtifactVersionDescription, opArtifactVersionDigest, opArtifactVersionHash, opArtifactVersionId, opArtifactVersionIsWeaveObject, opArtifactVersions, opArtifactVersionVersionId, opDict, opFilesystemArtifactWeaveType, opFilter, opFlatten, opMap, opProjectArtifactTypes, opRootProject, opTypeName } from "../../../../../../core"
import { useNodeValue } from "../../../../../../react"
import { UPDATE_ARTIFACT_DESCRIPTION } from './gql';

export const useAllObjectVersions = (entity: string, project: string): Loadable<Array<ObjectVersionDictType>> => {
    const allObjectVersions = useMemo(() => allObjectVersionsNode(entity, project), [entity, project])
    const asDictNode = opMap({arr: allObjectVersions, mapFn: constFunction({row: 'artifactVersion'}, ({row}) => {
        return opObjectVersionToDict(row as any)
    })})
    const value = useNodeValue(asDictNode)
    return useMemo(() => {
        if (value.loading) {
            return {loading: true}
        } else {
            return {
                loading: false,
                result: removeNonUserObjects(value.result)
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

///

type Loadable<T> = {loading: true} | {loading: false, result: T}

type ObjectVersionDictType = {
    artifact_id: string,
    collection_name: string,
    type_name: string,
    aliases: Array<string>,
    created_at_ms: number,
    description: string,
    hash: string,
    version_index: number,
}

const nonUserTypes = [
    'OpDef', 'list', 'dict', 'type', 'stream_table'
]
const removeNonUserObjects = (objectVersions: Array<ObjectVersionDictType>) => {
    return objectVersions.filter(objectVersion => {
        return !nonUserTypes.includes(objectVersion.type_name)
    })
}

const opObjectVersionToDict = (objectVersionNode: Node<'artifactVersion'>) => {
    const sequenceNode = opArtifactVersionArtifactSequence({artifactVersion: objectVersionNode})
    const artifactTypeNode = opArtifactVersionArtifactType({artifactVersion: objectVersionNode}) as Node<'artifactVersion'>
    return opDict({
        artifact_id: opArtifactVersionId({artifactVersion: objectVersionNode}),
        collection_name: opArtifactName({artifact: sequenceNode}),
        type_name: fnObjectVersionTypeVersion(artifactTypeNode),
        // type_name: opTypeName({type: opFilesystemArtifactWeaveType({artifact: objectVersionNode} as any)})
        aliases: opArtifactAliasAlias({artifactAlias:  opArtifactVersionAliases({artifactVersion: objectVersionNode})}),
        created_at_ms: opArtifactVersionCreatedAt({artifactVersion: objectVersionNode}),
        description: opArtifactVersionDescription({artifactVersion: objectVersionNode}),
        hash: fnObjectVersionHash(objectVersionNode),
        version_index :opArtifactVersionVersionId({artifactVersion: objectVersionNode}),
    } as any)
}

const fnObjectVersionTypeVersion = (objectVersionNode: Node<'artifactVersion'>) => {
    // TODO(tim/weaveflow_improved_nav): This is incorrect for now. We don't have the notion
    // of a type version yet in the weaveflow model. We Are going to make the simplifying assumption
    // that:
    // 1. The name of the artifactType is the same name as the weave type
    // 2. There is only 1 version of each type (totally wrong)
    return  opArtifactTypeName({artifactType: objectVersionNode})
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


