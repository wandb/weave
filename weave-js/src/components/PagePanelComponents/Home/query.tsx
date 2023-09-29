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
    num_logged_traces: number;
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
        projectHistoryType: opProjectHistoryType({project: row}),
      } as any);
    }),
  });

  const entityProjectNamesValue = useNodeValue(projectMetaNode);

  return useMemo(() => {
    // this filter step is done client side - very bad!
    const rawResult: Array<{
      name: string;
      updatedAt: number;
      num_boards: number;
      num_stream_tables: number;
      num_logged_tables: number;
      projectHistoryType: w.Type;
    }> = entityProjectNamesValue.result ?? [];
    const result: Array<{
      name: string;
      updatedAt: number;
      num_boards: number;
      num_stream_tables: number;
      num_logged_tables: number;
      num_logged_traces: number;
    }> = rawResult.map(r => {
      return {
        ...r,
        num_logged_traces: 0,
        // Uncomment this to enable legacy trace counting
        // and allow projects with such data to be displayed.
        // Waiting on performance
        // num_logged_traces: projectHistoryTypeToLegacyTraceKeys(
        //   r.projectHistoryType as w.Type
        // ).length,
      };
    });

    return {
      result: result.filter(
        res =>
          res.num_boards +
            res.num_logged_tables +
            res.num_stream_tables +
            res.num_logged_traces >
          0
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
    legacyTracesCount: number;
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
    projectHistoryType: opProjectHistoryType({project: projectNode}),
  } as any);
  const compositeValue = useNodeValue(compositeNode);

  return useMemo(() => {
    let result = {
      boardCount: 0,
      runStreamCount: 0,
      loggedTableCount: 0,
      legacyTracesCount: 0,
    };
    if (compositeValue.result != null) {
      const keys = projectHistoryTypeToLegacyTraceKeys(
        compositeValue.result.projectHistoryType as w.Type
      );

      result = {
        ...compositeValue.result,
        legacyTracesCount: keys.length,
      } as {
        boardCount: number;
        runStreamCount: number;
        loggedTableCount: number;
        legacyTracesCount: number;
      };
    }

    return {
      result,
      loading: compositeValue.loading,
    };
  }, [compositeValue.loading, compositeValue.result]) as {
    result: {
      boardCount: number;
      runStreamCount: number;
      loggedTableCount: number;
      legacyTracesCount: number;
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

const opProjectHistoryType = ({project}: {project: w.Node}) => {
  return w.callOpVeryUnsafe(
    'refine_history3_type',
    {run: w.opProjectRuns({project})},
    'type'
  );
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
        createdByUpdatedAt: w.opRunUpdatedAt({
          run: w.opArtifactVersionCreatedBy({
            artifactVersion: latestVersionNode,
          }),
        }),
        numRows: w.callOpVeryUnsafe(
          'run-historyLineCount',
          {
            run: w.opArtifactVersionCreatedBy({
              artifactVersion: latestVersionNode,
            }),
          },
          'number'
        ) as any,
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
    createdByUpdatedAt: number;
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

export const useProjectLegacyTraces = (
  entityName: string,
  projectName: string
): {
  result: Array<{
    name: string;
  }>;
  loading: boolean;
} => {
  const projectNode = w.opRootProject({
    entityName: w.constString(entityName),
    projectName: w.constString(projectName),
  });
  const historyTypeNode = opProjectHistoryType({project: projectNode});
  const historyTypeValue = useNodeValue(historyTypeNode as w.Node);
  return useMemo(() => {
    const keys =
      historyTypeValue.result == null
        ? []
        : projectHistoryTypeToLegacyTraceKeys(
            historyTypeValue.result as w.Type
          );
    return {
      result: keys.map(key => ({
        name: key,
      })),
      loading: historyTypeValue.loading,
    };
  }, [historyTypeValue.loading, historyTypeValue.result]);
};

const projectHistoryTypeToLegacyTraceKeys = (
  projectHistoryType: w.Type
): string[] => {
  if (w.isTaggedValue(projectHistoryType)) {
    projectHistoryType = projectHistoryType.value;
    if (w.isList(projectHistoryType)) {
      projectHistoryType = projectHistoryType.objectType;
      if (w.isTaggedValue(projectHistoryType)) {
        projectHistoryType = projectHistoryType.value;
        if (
          !w.isSimpleTypeShape(projectHistoryType) &&
          projectHistoryType.type === 'ArrowWeaveList'
        ) {
          projectHistoryType = projectHistoryType.objectType;
          if (w.isTypedDict(projectHistoryType)) {
            const legacyTraceKeys = Object.entries(
              projectHistoryType.propertyTypes
            )
              .filter(([key, value]) => {
                return (
                  value != null &&
                  w.isAssignableTo(
                    value,
                    w.maybe({
                      type: 'wb_trace_tree',
                    })
                  )
                );
              })
              .map(([key, value]) => key);
            return legacyTraceKeys;
          }
        }
      }
    }
  }
  return [];
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
    createdByUpdatedAt: number;
    numRows: number;
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
    createdByUpdatedAt: number;
    numRows: number;
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
