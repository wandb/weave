// This file contains the primary data fetch for the Home page.

import * as w from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {useMemo} from 'react';
import {
  getLocalArtifactDataNode,
  opFilterArtifactsToWeaveObjects,
} from '../../Panel2/PanelRootBrowser/util';
import {ASSUME_ALL_BOARDS_ARE_GROUP_ART_TYPE} from './dataModelAssumptions';

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

export const useProjectsForEntityWithWeaveObject = (
  entityName: string
): {
  result: Array<{
    name: string;
    updatedAt: number;
    num_boards: number;
    num_stream_tables: number;
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
        num_boards: opProjectBoardCount({project: row}),
        num_stream_tables: opProjectRunStreamCount({project: row}),
        num_logged_tables: opProjectLoggedTableCount({project: row}),
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
      num_stream_tables: number;
      num_logged_tables: number;
    }> = entityProjectNamesValue.result ?? [];

    return {
      result: result.filter(
        res =>
          res.num_boards + res.num_logged_tables + res.num_stream_tables > 0
      ),
      loading: entityProjectNamesValue.loading,
    };
  }, [entityProjectNamesValue.loading, entityProjectNamesValue.result]);
};

export const useProjectAssetCount = (
  entityName: string,
  projectName: string
): {
  result: {
    boardCount: number;
    runStreamCount: number;
    loggedTableCount: number;
  };
  loading: boolean;
} => {
  const projectNode = w.opRootProject({
    entityName: w.constString(entityName),
    projectName: w.constString(projectName),
  });
  const compositeNode = w.opDict({
    boardCount: opProjectBoardCount({project: projectNode}),
    runStreamCount: opProjectRunStreamCount({project: projectNode}),
    loggedTableCount: opProjectLoggedTableCount({project: projectNode}),
  } as any);
  const compositeValue = useNodeValue(compositeNode);

  return useMemo(
    () => ({
      result: compositeValue.result ?? {
        boardCount: 0,
        runStreamCount: 0,
        loggedTableCount: 0,
      },
      loading: compositeValue.loading,
    }),
    [compositeValue.loading, compositeValue.result]
  ) as {
    result: {
      boardCount: number;
      runStreamCount: number;
      loggedTableCount: number;
    };
    loading: boolean;
  };
};

const opProjectBoardCount = ({project}: {project: w.Node}) => {
  return w.opCount({arr: opProjectBoardArtifacts({project})});
};

const opProjectRunStreamCount = ({project}: {project: w.Node}) => {
  return w.opCount({arr: opProjectRunStreamArtifacts({project})});
};

const opProjectLoggedTableCount = ({project}: {project: w.Node}) => {
  return w.opCount({arr: opProjectRunLoggedTableArtifacts({project})});
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
    artifactType: w.constString('stream_table'),
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
  return w.constNode(w.list('artifact'), []);
  // There is currently a bug with RunLoggedTables in preview panel
  // temporarily disabling them. This bug is documented here:
  // https://wandb.atlassian.net/browse/WB-15157.
  //
  // The bug originated from
  // https://github.com/wandb/weave/commit/d34cf7af93dc06f32e1c931b2aec571c969304d5
  // which fixes board generation for StreamTables but broke for logged tables.
  //
  //
  // const artifactTypesNode = w.opProjectArtifactType({
  //   project,
  //   artifactType: w.constString('run_table'),
  // });
  // const artifactsNode = w.opArtifactTypeArtifacts({
  //   artifactType: artifactTypesNode,
  // });

  // return artifactsNode;
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

export const useLocalDashboards = (): {
  result: Array<{
    name: string;
    version: string;
    createdAt: number;
  }>;
  loading: boolean;
} => {
  const localPanelArtifacts = getLocalArtifactDataNode(true);

  const detailsNode = w.opMap({
    arr: localPanelArtifacts,
    mapFn: w.constFunction(
      {row: {type: 'FilesystemArtifact' as any}},
      ({row}) => {
        const nameNode = w.callOpVeryUnsafe(
          'FilesystemArtifact-artifactName',
          {
            artifact: row,
          },
          'string'
        ) as any;
        const versionNode = w.callOpVeryUnsafe(
          'FilesystemArtifact-artifactVersion',
          {
            artifact: row,
          },
          'string'
        ) as any;
        const createdAtNode = w.callOpVeryUnsafe(
          'FilesystemArtifact-createdAt',
          {
            artifact: row,
          },
          'string'
        ) as any;
        return w.opDict({
          name: nameNode,
          version: versionNode,
          createdAt: createdAtNode,
        } as any);
      }
    ),
  });

  const detailsValue = useNodeValue(detailsNode);

  return useMemo(() => {
    return {
      result: detailsValue.result ?? [],
      loading: detailsValue.loading,
    };
  }, [detailsValue.loading, detailsValue.result]);
};
