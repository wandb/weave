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
export const useUserName = (
  isAuthenticated?: boolean
): {
  result: string | undefined;
  loading: boolean;
} => {
  const entityNameNode = useMemo(
    () =>
      isAuthenticated
        ? w.opUserUsername({
            user: w.opRootViewer({}),
          })
        : w.constNone(),
    [isAuthenticated]
  );
  return useNodeValue(entityNameNode);
};

/**
 * Fetches the user's entities.
 */
export const useUserEntities = (
  isAuthenticated?: boolean
): {
  result: string[];
  loading: boolean;
} => {
  const entityNamesNode = useMemo(
    () =>
      isAuthenticated
        ? w.opEntityName({
            entity: w.opUserEntities({entity: w.opRootViewer({})}),
          })
        : w.constNode(w.list('string'), []),
    [isAuthenticated]
  );
  const entityNameValue = useNodeValue(entityNamesNode);
  return useMemo(
    () => ({
      result: entityNameValue.result ?? [],
      loading: entityNameValue.loading,
    }),
    [entityNameValue.loading, entityNameValue.result]
  );
};

// export const useProjectsForEntityWithWeaveObject = (
//   entityName: string
// ): {
//   result: string[];
//   loading: boolean;
// } => {
//   const projectsNode = w.opEntityProjects({
//     entity: w.opRootEntity({
//       entityName: w.constString(entityName),
//     }),
//   });
//   // TODO: filter to just projects that have weave objects
//   const entityProjectNamesNode = w.opProjectName({
//     project: projectsNode,
//   });
//   const entityProjectNamesValue = useNodeValue(entityProjectNamesNode);
//   return useMemo(
//     () => ({
//       result: entityProjectNamesValue.result ?? [],
//       loading: entityProjectNamesValue.loading,
//     }),
//     [entityProjectNamesValue.loading, entityProjectNamesValue.result]
//   );
// };

export const useProjectsForEntityWithWeaveObject = (
  entityName: string
): {
  result: Array<{
    name: string;
    updatedAt: number;
    num_boards: number;
    num_run_streams: number;
    num_logged_tables: number;
  }>;
  loading: boolean;
} => {
  const projectsNode = w.opEntityProjects({
    entity: w.opRootEntity({
      entityName: w.constString(entityName),
    }),
  });

  // Warning... this is going to be hella expensive.
  const projectMetaNode = w.opMap({
    arr: projectsNode,
    mapFn: w.constFunction({row: 'project'}, ({row}) => {
      return w.opDict({
        name: w.opProjectName({project: row}),
        updatedAt: w.opProjectUpdatedAt({project: row}),
        num_boards: w.opCount({arr: opProjectBoardArtifacts({project: row})}),
        num_run_streams: w.opCount({
          arr: opProjectRunStreamArtifacts({project: row}),
        }),
        num_logged_tables: w.opCount({
          arr: opProjectRunLoggedTableArtifacts({project: row}),
        }),
      } as any);
    }),
  });

  const entityProjectNamesValue = useNodeValue(projectMetaNode);

  return useMemo(() => {
    // this filter step is done client side - very bad!
    const result: Array<{
      name: string;
      updatedAt: number;
      num_boards: number;
      num_run_streams: number;
      num_logged_tables: number;
    }> = entityProjectNamesValue.result ?? [];

    return {
      result: result.filter(
        res => res.num_boards + res.num_logged_tables + res.num_run_streams > 0
      ),
      loading: entityProjectNamesValue.loading,
    };
  }, [entityProjectNamesValue.loading, entityProjectNamesValue.result]);
};

const projectBoardsNode = (entityName: string, projectName: string) => {
  const projectNode = w.opRootProject({
    entityName: w.constString(entityName),
    projectName: w.constString(projectName),
  });

  return opProjectBoardArtifacts({project: projectNode});
};

const opProjectBoardArtifacts = ({project}: {project: w.Node}) => {
  let artifactsNode;
  if (ASSUME_ALL_BOARDS_ARE_GROUP_ART_TYPE) {
    const artifactTypesNode = w.opProjectArtifactType({
      project,
      artifactType: w.constString('Group'),
    });
    artifactsNode = w.opArtifactTypeArtifacts({
      artifactType: artifactTypesNode,
    });
  } else {
    const artifactTypesNode = w.opProjectArtifactTypes({
      project,
    });
    artifactsNode = w.opFlatten({
      arr: w.opArtifactTypeArtifacts({
        artifactType: artifactTypesNode,
      }) as any,
    });
  }

  return opFilterArtifactsToWeaveObjects(artifactsNode, true);
};

const projectTablesNode = (entityName: string, projectName: string) => {
  const projectNode = w.opRootProject({
    entityName: w.constString(entityName),
    projectName: w.constString(projectName),
  });

  return opProjectRunStreamArtifacts({project: projectNode});
};

const opProjectRunStreamArtifacts = ({project}: {project: w.Node}) => {
  const artifactTypesNode = w.opProjectArtifactType({
    project,
    artifactType: w.constString('run_stream'),
  });
  const artifactsNode = w.opArtifactTypeArtifacts({
    artifactType: artifactTypesNode,
  });

  return opFilterArtifactsToWeaveObjects(artifactsNode, false);
};

const projectRunLoggedTablesNode = (
  entityName: string,
  projectName: string
) => {
  const projectNode = w.opRootProject({
    entityName: w.constString(entityName),
    projectName: w.constString(projectName),
  });

  return opProjectRunLoggedTableArtifacts({project: projectNode});
};

const opProjectRunLoggedTableArtifacts = ({project}: {project: w.Node}) => {
  const artifactTypesNode = w.opProjectArtifactType({
    project,
    artifactType: w.constString('run_table'),
  });
  const artifactsNode = w.opArtifactTypeArtifacts({
    artifactType: artifactTypesNode,
  });

  return artifactsNode;
};

// Bad Weave-form... just materializing the data
const opArtifactsBasicMetadata = ({artifacts}: {artifacts: w.Node}) => {
  return w.opMap({
    arr: artifacts,
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
};

export const useProjectBoards = (
  entityName: string,
  projectName: string
): {
  result: Array<{
    name: string;
    createdByUserName: string;
    createdAt: number;
    updatedAt: number;
  }>;
  loading: boolean;
} => {
  const filteredArtifactsNode = projectBoardsNode(entityName, projectName);
  const boardDetailsNode = opArtifactsBasicMetadata({
    artifacts: filteredArtifactsNode,
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

export const useProjectRunStreams = (
  entityName: string,
  projectName: string
): {
  result: Array<{
    name: string;
    createdByUserName: string;
    createdAt: number;
    updatedAt: number;
  }>;
  loading: boolean;
} => {
  const filteredArtifactsNode = projectTablesNode(entityName, projectName);
  const boardDetailsNode = opArtifactsBasicMetadata({
    artifacts: filteredArtifactsNode,
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

export const useProjectRunLoggedTables = (
  entityName: string,
  projectName: string
): {
  result: Array<{
    name: string;
    createdByUserName: string;
    createdAt: number;
    updatedAt: number;
  }>;
  loading: boolean;
} => {
  const filteredArtifactsNode = projectRunLoggedTablesNode(
    entityName,
    projectName
  );
  const boardDetailsNode = opArtifactsBasicMetadata({
    artifacts: filteredArtifactsNode,
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
