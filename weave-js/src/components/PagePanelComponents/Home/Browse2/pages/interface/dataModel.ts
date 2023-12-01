import { useMemo } from "react"

import { constFunction, constString, Node, opArtifactAliasAlias, opArtifactName, opArtifactTypeArtifacts, opArtifactTypeName, opArtifactVersionAliases, opArtifactVersionArtifactSequence, opArtifactVersionArtifactType, opArtifactVersionCreatedAt, opArtifactVersionDescription, opArtifactVersionDigest, opArtifactVersionIsWeaveObject, opArtifactVersions, opArtifactVersionVersionId, opDict, opFilesystemArtifactWeaveType, opFilter, opFlatten, opMap, opProjectArtifactTypes, opRootProject, opTypeName } from "../../../../../../core"
import { useNodeValue } from "../../../../../../react"

type Loadable<T> = {loading: true} | {loading: false, result: T}

type ObjectVersionDictType = {
    collection_name: string,
    type_name: string,
    aliases: Array<string>,
    created_at_ms: number,
    description: string,
    digest: string,
    version_index: number,
}

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

///
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
    const artifactTypeNode = opArtifactVersionArtifactType({artifactVersion: objectVersionNode})
    return opDict({
        collection_name: opArtifactName({artifact: sequenceNode}),
        type_name: opArtifactTypeName({artifactType: artifactTypeNode}),
        // type_name: opTypeName({type: opFilesystemArtifactWeaveType({artifact: objectVersionNode} as any)})
        aliases: opArtifactAliasAlias({artifactAlias:  opArtifactVersionAliases({artifactVersion: objectVersionNode})}),
        created_at_ms: opArtifactVersionCreatedAt({artifactVersion: objectVersionNode}),
        description: opArtifactVersionDescription({artifactVersion: objectVersionNode}),
        digest: opArtifactVersionDigest({artifactVersion: objectVersionNode}),
        version_index :opArtifactVersionVersionId({artifactVersion: objectVersionNode}),
    } as any)
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
