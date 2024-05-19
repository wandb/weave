// This file provides utilities for artifact dependencies.
import {
  constFunction,
  constString,
  isVoidNode,
  listObjectType,
  Node,
  opArray,
  opArtifactAliasAlias,
  opArtifactProject,
  opArtifactVersionAliases,
  opArtifactVersionArtifactSequence,
  opArtifactVersionCreatedAt,
  opArtifactVersionCreatedBy,
  opArtifactVersionDependencyOf,
  opContains,
  opDict,
  opEntityName,
  opFilter,
  opMap,
  opPick,
  opProjectEntity,
  opProjectName,
  opRunUser,
  opSort,
  opUserUsername,
  typedDict,
  voidNode,
} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';

const getArtifactDependencyOfForNode = (node: Node<'artifactVersion'>) => {
  const dependencyOfNode = opArtifactVersionDependencyOf({
    artifactVersion: node,
  });

  const artifactSeqDetails = opMap({
    arr: dependencyOfNode as any,
    mapFn: constFunction({row: 'artifactVersion'}, ({row}) =>
      opDict({
        aliases: opMap({
          arr: opArtifactVersionAliases({
            artifactVersion: row,
          }),
          mapFn: constFunction({row: 'artifactAlias'}, ({row: rowAlias}) =>
            opArtifactAliasAlias({
              artifactAlias: rowAlias,
            })
          ),
        }),
        createdAt: opArtifactVersionCreatedAt({
          artifactVersion: row,
        }),
        createdByUsername: opUserUsername({
          user: opRunUser({
            run: opArtifactVersionCreatedBy({
              artifactVersion: row,
            }),
          }),
        }),
        artifactSequence: opArtifactVersionArtifactSequence({
          artifactVersion: row,
        }),
        projectName: opProjectName({
          project: opArtifactProject({
            artifact: opArtifactVersionArtifactSequence({
              artifactVersion: row,
            }),
          }),
        }),
        entityName: opEntityName({
          entity: opProjectEntity({
            project: opArtifactProject({
              artifact: opArtifactVersionArtifactSequence({
                artifactVersion: row,
              }),
            }),
          }),
        }),
      } as any)
    ),
  });

  const filteredToLatest = opSort({
    arr: opFilter({
      arr: artifactSeqDetails,
      filterFn: constFunction(
        {row: listObjectType(artifactSeqDetails.type)},
        ({row}) =>
          opContains({
            arr: opPick({
              obj: row,
              key: constString('aliases'),
            }),
            element: constString('latest'),
          })
      ),
    }),
    compFn: constFunction({row: typedDict({})}, ({row}) => {
      return opArray({
        a: opPick({
          obj: row,
          key: constString('createdAt'),
        }),
      } as any);
    }),
    columnDirs: opArray({
      a: constString('desc'),
    } as any),
  });

  return filteredToLatest;
};

export const useArtifactDependencyOfForNode = (
  node: Node<'artifactVersion'> | null
): {
  loading: boolean;
  result: Array<{
    entityName: string;
    projectName: string;
    createdAt: number;
    createdByUsername: string;
    artifactSequence: {
      id: string;
      name: string;
    };
  }>;
} => {
  const resultNode =
    node != null ? getArtifactDependencyOfForNode(node) : voidNode();
  const res = useNodeValue(resultNode, {
    skip: isVoidNode(resultNode),
  });
  if (res.result == null) {
    res.result = [];
  }
  return res;
};
