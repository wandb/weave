// This file contains the primary data fetch for the Home page.

import * as w from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {useMemo} from 'react';
import {opFilterArtifactsToWeaveObjects} from '../../Panel2/PanelRootBrowser/util';
import {ASSUME_ALL_BOARDS_ARE_GROUP_ART_TYPE} from './dataModelAssumptions';

// type EngineEnvironmentType = 'wandb' | 'local' | 'colab';
// /**
//  *
//  */
// const getEngineEnvironment = (): EngineEnvironmentType => {
//   return 'wandb';
// };

// /**
//  * Fetches the recent boards for the current user.
//  */
// const getRecentBoards = () => {
//   return [];
// };

// /**
//  * Fetches the recent tables for the current user.
//  */
// const getRecentTables = () => {
//   return [];
// };

/**
 * Fetches the user entities.
 */
export const useUserName = (): {
  result: string | undefined;
  loading: boolean;
} => {
  const entityNameNode = w.opUserUsername({
    user: w.opRootViewer({}),
  });
  return useNodeValue(entityNameNode);
};

/**
 * Fetches the user's entities.
 */
export const useUserEntities = (): {
  result: string[];
  loading: boolean;
} => {
  const entityNamesNode = w.opEntityName({
    entity: w.opUserEntities({entity: w.opRootViewer({})}),
  });
  const entityNameValue = useNodeValue(entityNamesNode);
  return useMemo(
    () => ({
      result: entityNameValue.result ?? [],
      loading: entityNameValue.loading,
    }),
    [entityNameValue.loading, entityNameValue.result]
  );
};

export const useProjectsForEntityWithWeaveObject = (
  entityName: string
): {
  result: string[];
  loading: boolean;
} => {
  const projectsNode = w.opEntityProjects({
    entity: w.opRootEntity({
      entityName: w.constString(entityName),
    }),
  });
  // TODO: filter to just projects that have weave objects
  const entityProjectNamesNode = w.opProjectName({
    project: projectsNode,
  });
  const entityProjectNamesValue = useNodeValue(entityProjectNamesNode);
  return useMemo(
    () => ({
      result: entityProjectNamesValue.result ?? [],
      loading: entityProjectNamesValue.loading,
    }),
    [entityProjectNamesValue.loading, entityProjectNamesValue.result]
  );
};

const projectBoardsNode = (entityName: string, projectName: string) => {
  const projectNode = w.opRootProject({
    entityName: w.constString(entityName),
    projectName: w.constString(projectName),
  });

  let artifactsNode;
  if (ASSUME_ALL_BOARDS_ARE_GROUP_ART_TYPE) {
    const artifactTypesNode = w.opProjectArtifactType({
      project: projectNode,
      artifactType: w.constString('Group'),
    });
    artifactsNode = w.opArtifactTypeArtifacts({
      artifactType: artifactTypesNode,
    });
  } else {
    const artifactTypesNode = w.opProjectArtifactTypes({
      project: projectNode,
    });
    artifactsNode = w.opFlatten({
      arr: w.opArtifactTypeArtifacts({
        artifactType: artifactTypesNode,
      }) as any,
    });
  }

  return opFilterArtifactsToWeaveObjects(artifactsNode, true);
};

// Bad Weave-form... just materializing the data
export const useProjectBoards = (
  entityName: string,
  projectName: string
): {
  result: {
    name: string;
    createdByUserName: string;
    createdAt: number;
    updatedAt: number;
  }[];
  loading: boolean;
} => {
  const filteredArtifactsNode = projectBoardsNode(entityName, projectName);
  const boardDetailsNode = w.opMap({
    arr: filteredArtifactsNode,
    mapFn: w.constFunction({row: 'artifact' as const}, ({row}) => {
      const latestVersionNode = w.opArtifactMembershipArtifactVersion({
        artifactMembership: w.opArtifactMembershipForAlias({
          artifact: row,
          aliasName: w.constString('latest'),
        }),
      });
      return w.opDict({
        name: w.opArtifactName({
          artifact: row,
        }),
        createdByUserName: w.opUserName({
          user: w.opRunUser({
            run: w.opArtifactVersionCreatedBy({
              artifactVersion: latestVersionNode,
            }),
          }),
        }),
        createdAt: w.opArtifactCreatedAt({artifact: row}),
        updatedAt: w.opArtifactVersionCreatedAt({
          artifactVersion: latestVersionNode,
        }),
      } as any);
    }),
  });
  const artifactDetailsValue = useNodeValue(boardDetailsNode);
  return useMemo(
    () => ({
      result: artifactDetailsValue.result ?? [],
      loading: artifactDetailsValue.loading,
    }),
    [artifactDetailsValue.loading, artifactDetailsValue.result]
  );
};
