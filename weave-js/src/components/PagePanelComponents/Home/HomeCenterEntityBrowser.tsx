import * as globals from '@wandb/weave/common/css/globals.styles';
import {TargetBlank} from '@wandb/weave/common/util/links';
import {
  IconAddNew,
  IconChevronDown,
  IconCopy,
  IconDelete,
  IconFullScreenModeExpand,
  IconInfo,
  IconLightbulbInfo,
  IconOpenNewTab,
} from '@wandb/weave/components/Icon';
import {useWeaveContext} from '@wandb/weave/context';
import {
  constString,
  directlyConstructOpCall,
  list,
  Node,
  opConcat,
  opFilesystemArtifactFile,
  opFileTable,
  opGet,
  opIsNone,
  opPick,
  opProjectRuns,
  opRootProject,
  opRunHistory3,
  opStreamTableRows,
  opTableRows,
} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {setDocumentTitle} from '@wandb/weave/util/document';
import moment from 'moment';
import React, {useEffect, useMemo, useState} from 'react';
import {useHistory, useParams} from 'react-router-dom';
import styled from 'styled-components';

import {
  urlEntity,
  urlProject,
  urlProjectAssetPreview,
  urlProjectAssets,
} from '../../../urls';
import {urlWandbFrontend} from '../../../util/urls';
import {SpanWeaveWithTimestampType} from '../../Panel2/PanelTraceTree/util';
import {useMakeLocalBoardFromNode} from '../../Panel2/pyBoardGen';
import {NavigateToExpressionType, SetPreviewNodeType} from './common';
import {HomeParams} from './Home';
import {CenterBrowser, CenterBrowserActionType} from './HomeCenterBrowser';
import {
  HomePreviewSidebarTemplate,
  SafeHomeExpressionPreviewParts,
  SEED_BOARD_OP_NAME,
} from './HomePreviewSidebar';
import * as LayoutElements from './LayoutElements';
import * as query from './query';

type CenterEntityBrowserPropsType = {
  entityName: string;
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
};

export const CenterEntityBrowser: React.FC<
  CenterEntityBrowserPropsType
> = props => {
  const params = useParams<HomeParams>();
  if (params.project == null) {
    return <CenterEntityBrowserInner {...props} />;
  } else {
    return <CenterProjectBrowser {...props} projectName={params.project} />;
  }
};

type CenterEntityBrowserInnerPropsType = CenterEntityBrowserPropsType;

export const CenterEntityBrowserInner: React.FC<
  CenterEntityBrowserInnerPropsType
> = props => {
  const {entityName} = props;
  const history = useHistory();
  const browserTitle = props.entityName;
  const projectsMeta = query.useProjectsForEntityWithWeaveObject(entityName);

  useEffect(() => {
    setDocumentTitle(entityName);
  }, [entityName]);

  const browserData = useMemo(() => {
    // TODO: make sorting more customizable and awesome
    const sortedMeta = [...projectsMeta.result].sort(
      (a, b) => b.updatedAt - a.updatedAt
    );
    return sortedMeta.map(meta => ({
      _id: meta.name,
      entity: entityName,
      project: meta.name,
      boards: (meta.num_boards ?? 0) > 0 ? meta.num_boards : null,
      tables:
        (meta.num_stream_tables + meta.num_logged_tables ?? 0) > 0
          ? meta.num_stream_tables + meta.num_logged_tables
          : null,
      'run logged traces':
        meta.num_logged_traces > 0 ? meta.num_logged_traces : null,
      'updated at': moment.utc(meta.updatedAt).local().calendar(),
    }));
  }, [projectsMeta.result, entityName]);

  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(() => {
    return [
      [
        {
          icon: IconChevronDown,
          label: 'Browse project',
          onClick: row => {
            history.push(urlProject(row.entity, row.project));
          },
        },
      ],
      [
        {
          icon: IconOpenNewTab,
          label: 'View in Weights and Biases',
          onClick: row => {
            // Open a new tab with the W&B project URL
            const prefix = urlWandbFrontend();
            const url = `${prefix}/${props.entityName}/${row.project}/overview`;
            // eslint-disable-next-line wandb/no-unprefixed-urls
            window.open(url, '_blank');
          },
        },
      ],
    ];
  }, [props, history]);

  const loading = projectsMeta.loading;

  return (
    <CenterBrowser
      allowSearch
      noDataCTA={`No projects with Weave assets found for entity: ${props.entityName}`}
      columns={[
        'project',
        'boards',
        'tables',
        // 'run logged traces', // keeping this hidden for now to not draw attention
        'updated at',
      ]}
      loading={loading}
      title={browserTitle}
      data={browserData}
      actions={browserActions}
    />
  );
};

type CenterProjectBrowserPropsType = CenterEntityBrowserInnerPropsType & {
  projectName: string;
};
const CenterProjectBrowser: React.FC<CenterProjectBrowserPropsType> = props => {
  const history = useHistory();
  const params = useParams<HomeParams>();
  const {entityName, projectName} = props;

  const noAccessNode = opIsNone({
    val: opRootProject({
      entityName: constString(entityName),
      projectName: constString(projectName),
    }),
  });
  const noAccessValueNode = useNodeValue(noAccessNode);

  // This effect automatically kicks back to the root if the project is not
  // accessible - which occurs when you change states.
  useEffect(() => {
    if (!noAccessValueNode.loading && noAccessValueNode.result) {
      history.push(urlEntity(entityName));
    }
  }, [
    noAccessValueNode.loading,
    noAccessValueNode.result,
    history,
    entityName,
    projectName,
  ]);

  if (params.assetType == null) {
    return <CenterProjectBrowserInner {...props} />;
  } else if (params.assetType === 'board') {
    return <CenterProjectBoardsBrowser {...props} />;
  } else if (params.assetType === 'table') {
    return <CenterProjectTablesBrowser {...props} />;
  } else if (params.assetType === 'run_logged_trace') {
    return <CenterProjectLegacyTracesBrowser {...props} />;
  } else {
    return <>Not implemented</>;
  }
};

type CenterProjectBrowserInnerPropsType = {
  entityName: string;
  projectName: string;
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
};

const CenterProjectBrowserInner: React.FC<
  CenterProjectBrowserInnerPropsType
> = props => {
  const history = useHistory();
  const params = useParams<HomeParams>();

  useEffect(() => {
    const title = `${params.entity}/${params.project}`;
    setDocumentTitle(title);
  }, [params.entity, params.project]);

  const browserTitle = props.projectName;
  const assetCounts = query.useProjectAssetCount(
    props.entityName,
    props.projectName
  );
  const browserData = useMemo(() => {
    return [
      {
        _id: 'board',
        'asset type': 'Boards',
        count: assetCounts.result.boardCount ?? 0,
      },
      {
        _id: 'table',
        'asset type': 'Tables',
        count:
          (assetCounts.result.loggedTableCount ?? 0) +
          (assetCounts.result.runStreamCount ?? 0),
      },
      ...(assetCounts.result.legacyTracesCount === 0
        ? []
        : [
            {
              _id: 'run_logged_trace',
              'asset type': 'Run Logged Traces',
              count: assetCounts.result.legacyTracesCount ?? 0,
            },
          ]),
      // TODO: Let's skip objects for the MVP
      // {
      //   _id: 'objects',
      //   'asset type': 'Objects',
      //   // TODO: get these from the server
      //   // 'count': 5,
      //   // 'last edited': 'yesterday',
      // },
    ];
  }, [
    assetCounts.result.boardCount,
    assetCounts.result.legacyTracesCount,
    assetCounts.result.loggedTableCount,
    assetCounts.result.runStreamCount,
  ]);

  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(() => {
    return [
      [
        {
          icon: IconChevronDown,
          label: 'Browse asset type',
          onClick: row => {
            history.push(
              urlProjectAssets(params.entity!, params.project!, row._id)
            );
          },
        },
      ],
    ];
  }, [history, params.entity, params.project]);

  return (
    <CenterBrowser
      title={browserTitle}
      loading={assetCounts.loading}
      breadcrumbs={[
        {
          key: 'entity',
          text: props.entityName,
          onClick: () => {
            props.setPreviewNode(undefined);
            history.push(urlEntity(props.entityName));
          },
        },
      ]}
      data={browserData}
      actions={browserActions}
      columns={['asset type', 'count']}
    />
  );
};

const rowToExpression = (
  entityName: string,
  projectName: string,
  artName: string
) => {
  const uri = `wandb-artifact:///${entityName}/${projectName}/${artName}:latest/obj`;
  return opGet({uri: constString(uri)});
};

const CenterProjectBoardsBrowser: React.FC<
  CenterProjectBrowserInnerPropsType
> = ({entityName, projectName, setPreviewNode, navigateToExpression}) => {
  const history = useHistory();
  const params = useParams<HomeParams>();
  const browserTitle = 'Boards';
  const [deletingId, setDeletingId] = useState<string | undefined>();
  useEffect(() => {
    setDocumentTitle(
      params.preview
        ? `${params.preview} Preview`
        : `${params.entity}/${params.project} ${browserTitle}`
    );
  }, [params.entity, params.project, params.preview, browserTitle]);

  const boards = query.useProjectBoards(entityName, projectName);
  const browserData = useMemo(() => {
    return boards.result.map(b => ({
      _id: b.name,
      name: b.name,
      'updated at': moment.utc(b.updatedAt).local().calendar(),
      'created at': moment.utc(b.createdAt).local().calendar(),
      'created by': b.createdByUserName,
    }));
  }, [boards]);

  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(() => {
    return [
      [
        {
          icon: IconOpenNewTab,
          label: 'Open board',
          onClick: row => {
            navigateToExpression(
              rowToExpression(params.entity!, params.project!, row._id)
            );
          },
        },
        {
          icon: IconInfo,
          label: 'Board details',
          onClick: row => {
            history.push(
              urlProjectAssetPreview(
                params.entity!,
                params.project!,
                params.assetType === 'board' ? 'board' : 'table',
                row._id
              )
            );
          },
        },
      ],
      [
        {
          icon: IconDelete,
          label: 'Delete board',
          onClick: row => {
            const uri = `wandb-artifact:///${entityName}/${projectName}/${row._id}:latest/obj`;
            setDeletingId(uri);
          },
        },
      ],
    ];
  }, [
    history,
    params.entity,
    params.project,
    params.assetType,
    entityName,
    projectName,
    navigateToExpression,
  ]);

  const sidebarActions = useMemo(
    () =>
      browserActions.map((actionSection, index) => {
        if (index === 0) {
          return actionSection.filter(
            action => action.label !== 'Board details'
          );
        }
        return actionSection;
      }),
    [browserActions]
  );

  useEffect(() => {
    if (params.preview) {
      const row = browserData.find(b => b._id === params.preview);
      if (!row) {
        setPreviewNode(undefined);
        return;
      }
      const expr = rowToExpression(
        params.entity!,
        params.project!,
        params.preview
      );
      const node = (
        <HomePreviewSidebarTemplate
          title={params.preview}
          row={row}
          actions={sidebarActions}
          setPreviewNode={setPreviewNode}
          primaryAction={{
            icon: IconOpenNewTab,
            label: `Open board`,
            onClick: () => {
              navigateToExpression(expr);
            },
          }}>
          <SafeHomeExpressionPreviewParts
            expr={expr}
            navigateToExpression={navigateToExpression}
          />
        </HomePreviewSidebarTemplate>
      );
      setPreviewNode(node);
    } else {
      setPreviewNode(undefined);
    }
  }, [
    history,
    params.entity,
    params.project,
    params.preview,
    setPreviewNode,
    navigateToExpression,
    sidebarActions,
    browserData,
  ]);

  return (
    <CenterBrowser
      allowSearch
      title={browserTitle}
      selectedRowId={params.preview}
      setPreviewNode={setPreviewNode}
      deletingId={deletingId}
      setDeletingId={setDeletingId}
      deleteTypeString="board"
      noDataCTA={`No Weave boards found for project: ${entityName}/${projectName}`}
      breadcrumbs={[
        {
          key: 'entity',
          text: entityName,
          onClick: () => {
            setPreviewNode(undefined);
            history.push(urlEntity(entityName));
          },
        },
        {
          key: 'project',
          text: projectName,
          onClick: () => {
            setPreviewNode(undefined);
            history.push(urlProject(entityName, projectName));
          },
        },
      ]}
      loading={boards.loading}
      columns={['name', 'updated at', 'created at', 'created by']}
      data={browserData}
      actions={browserActions}
    />
  );
};

const legacyTraceRowToSimpleNode = (
  entityName: string,
  projectName: string,
  legacyTraceKey: string
) => {
  return opPick({
    obj: opConcat({
      arr: opRunHistory3({
        run: opProjectRuns({
          project: opRootProject({
            entityName: constString(entityName),
            projectName: constString(projectName),
          }),
        }),
      }),
    }),
    key: constString(legacyTraceKey),
  }) as Node<{type: 'wb_trace_tree'}>;
};

const opWBTraceTreeConvertToSpans = (inputs: {
  tree: Node<{type: 'wb_trace_tree'}>;
}) => {
  return directlyConstructOpCall(
    'wb_trace_tree-convertToSpans',
    inputs,
    list(list(SpanWeaveWithTimestampType))
  );
};

const convertSimpleLegacyNodeToNewFormat = (
  node: Node<{type: 'wb_trace_tree'}>
) => {
  return opConcat({
    arr: opWBTraceTreeConvertToSpans({
      tree: node,
    }),
  });
};

const CenterProjectLegacyTracesBrowser: React.FC<
  CenterProjectBrowserInnerPropsType
> = ({entityName, projectName, setPreviewNode, navigateToExpression}) => {
  const history = useHistory();
  const params = useParams<HomeParams>();
  const browserTitle = 'Run Logged Traces';
  const weave = useWeaveContext();
  useEffect(() => {
    setDocumentTitle(
      params.preview
        ? `${params.preview} Preview`
        : `${params.entity}/${params.project} ${browserTitle}`
    );
  }, [params.entity, params.project, params.preview, browserTitle]);

  const legacyTraces = query.useProjectLegacyTraces(entityName, projectName);
  const browserData = useMemo(() => {
    return legacyTraces.result.map(b => ({
      _id: b.name,
      name: b.name,
      // 'created at': moment.utc(b.createdAt).local().calendar(),
    }));
  }, [legacyTraces]);

  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(
    () => [
      [
        {
          icon: IconInfo,
          label: 'Table overview',
          onClick: row => {
            history.push(
              urlProjectAssetPreview(
                entityName,
                projectName,
                'run_logged_trace',
                row._id
              )
            );
          },
        },
        {
          icon: IconCopy,
          label: 'Copy Weave expression',
          onClick: row => {
            const node = legacyTraceRowToSimpleNode(
              entityName,
              projectName,
              row._id
            );
            const copyText = weave.expToString(node);
            navigator.clipboard.writeText(copyText).then(() => {
              // give user feedback
            });
          },
        },
      ],
    ],
    [history, entityName, projectName, weave]
  );

  useEffect(() => {
    if (legacyTraces.loading) {
      return;
    }
    if (params.preview) {
      const row = browserData.find(b => b._id === params.preview);
      if (!row) {
        setPreviewNode(undefined);
        return;
      }
      const expr = legacyTraceRowToSimpleNode(
        params.entity!,
        params.project!,
        row._id
      );
      const node = (
        <HomePreviewSidebarTemplate
          title={row.name}
          row={row}
          actions={[
            [
              {
                icon: IconFullScreenModeExpand,
                label: 'Preview Traces',
                onClick: _ => {
                  navigateToExpression(expr);
                },
              },
            ],
          ]}
          setPreviewNode={setPreviewNode}>
          <SafeHomeExpressionPreviewParts
            expr={convertSimpleLegacyNodeToNewFormat(expr)}
            generatorAllowList={['py_board-trace_monitor']}
            navigateToExpression={navigateToExpression}
          />
        </HomePreviewSidebarTemplate>
      );
      setPreviewNode(node);
    } else {
      setPreviewNode(undefined);
    }
  }, [
    browserData,
    history,
    params.entity,
    params.project,
    params.preview,
    setPreviewNode,
    navigateToExpression,
    legacyTraces.loading,
  ]);

  return (
    <>
      <CenterBrowser
        allowSearch
        title={browserTitle}
        selectedRowId={params.preview}
        noDataCTA={`No run logged traces found for project: ${entityName}/${projectName}`}
        breadcrumbs={[
          {
            key: 'entity',
            text: entityName,
            onClick: () => {
              setPreviewNode(undefined);
              history.push(urlEntity(entityName));
            },
          },
          {
            key: 'project',
            text: projectName,
            onClick: () => {
              setPreviewNode(undefined);
              history.push(urlProject(entityName, projectName));
            },
          },
        ]}
        loading={legacyTraces.loading}
        columns={['name']}
        data={browserData}
        actions={browserActions}
      />
    </>
  );
};

const tableRowToNode = (
  kind: string,
  entityName: string,
  projectName: string,
  artName: string
) => {
  let newExpr: Node;
  if (kind === 'Stream Table') {
    const uri = `wandb-artifact:///${entityName}/${projectName}/${artName}:latest/obj`;
    const node = opGet({uri: constString(uri)});
    node.type = {type: 'stream_table'} as any;
    newExpr = opStreamTableRows({
      self: node as any,
    });
  } else {
    // This is a hack. Would be nice to have better mapping
    // Note that this will not work for tables with spaces in their name
    // as we strip the space out to make the artifact name.
    const artNameParts = artName.split('-', 3);
    const tableName = artNameParts[artNameParts.length - 1] + '.table.json';

    const uri = `wandb-artifact:///${entityName}/${projectName}/${artName}:latest`;
    newExpr = opTableRows({
      table: opFileTable({
        file: opFilesystemArtifactFile({
          artifactVersion: opGet({
            uri: constString(uri),
          }) as any,
          path: constString(tableName),
        }),
      }),
    });
  }
  return newExpr;
};

const CenterProjectTablesBrowser: React.FC<
  CenterProjectBrowserInnerPropsType
> = ({entityName, projectName, setPreviewNode, navigateToExpression}) => {
  const history = useHistory();
  const params = useParams<HomeParams>();
  const weave = useWeaveContext();
  const makeBoardFromNode = useMakeLocalBoardFromNode();
  const [deletingId, setDeletingId] = useState<string | undefined>();

  const browserTitle = 'Tables';
  useEffect(() => {
    if (params.preview) {
      setDocumentTitle(params.preview);
    } else {
      const title = `${params.entity}/${params.project} ${browserTitle}`;
      setDocumentTitle(title);
    }
  }, [params.entity, params.project, params.preview, browserTitle]);

  const runStreams = query.useProjectRunStreams(entityName, projectName);
  const loggedTables = query.useProjectRunLoggedTables(entityName, projectName);
  const isLoading = runStreams.loading || loggedTables.loading;
  const browserData = useMemo(() => {
    if (isLoading) {
      return [];
    }
    const streams = runStreams.result.map(b => ({
      _id: b.name,
      _updatedAt: b.updatedAt,
      name: b.name,
      kind: 'Stream Table',
      // Here we make the assumption that the run creating this artifact
      // is the underlying stream table pointed to by the artifact. This is
      // not strictly true, but is always true for the current implementation.
      // This approach saves us from having to execute multiple queries
      // since we don't need to load the stream table files to determine
      // the run id.
      'updated at': moment.utc(b.createdByUpdatedAt).local().calendar(),
      'created at': moment.utc(b.createdAt).local().calendar(),
      'created by': b.createdByUserName,
      'number of rows': b.numRows,
    }));
    const logged = loggedTables.result.map(b => ({
      _id: b.name,
      _updatedAt: b.updatedAt,
      name: b.name,
      kind: 'Logged Table',
      'updated at': moment.utc(b.updatedAt).local().calendar(),
      'created at': moment.utc(b.createdAt).local().calendar(),
      'created by': b.createdByUserName,
      // we use the # of steps in the run history to compute rows quickly. This works for stream tables
      // because the table leverages run history. For logged tables, we must open the table in order
      // to know the number of rows which is a much more expensive operation. Instead, we will just
      // display a dummy placeholder
      'number of rows': '-',
    }));
    const combined = [...streams, ...logged];
    combined.sort((a, b) => b._updatedAt - a._updatedAt);
    return combined;
  }, [isLoading, loggedTables.result, runStreams.result]);

  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(
    () => [
      [
        // Home Page TODO: Enable awesome previews
        {
          icon: IconInfo,
          label: 'Table overview',
          onClick: row => {
            history.push(
              urlProjectAssetPreview(entityName, projectName, 'table', row._id)
            );
          },
        },
        {
          icon: IconFullScreenModeExpand,
          label: 'Preview table',
          disabled: row => row['number of rows'] === 0,
          onClick: row => {
            navigateToExpression(
              tableRowToNode(row.kind, entityName, projectName, row._id)
            );
          },
        },
        {
          icon: IconCopy,
          label: 'Copy Weave expression',
          disabled: row => row['number of rows'] === 0,
          onClick: row => {
            const node = tableRowToNode(
              row.kind,
              entityName,
              projectName,
              row._id
            );
            const copyText = weave.expToString(node);
            navigator.clipboard.writeText(copyText).then(() => {
              // give user feedback
            });
          },
        },
      ],
      [
        {
          icon: IconAddNew,
          label: 'New board',
          disabled: row => row['number of rows'] === 0,
          onClick: row => {
            const node = tableRowToNode(
              row.kind,
              entityName,
              projectName,
              row._id
            );
            makeBoardFromNode(SEED_BOARD_OP_NAME, node, newDashExpr => {
              navigateToExpression(newDashExpr);
            });
          },
        },
      ],
      [
        {
          icon: IconDelete,
          label: 'Delete table',
          onClick: row => {
            const uri = `wandb-artifact:///${entityName}/${projectName}/${row._id}:latest/obj`;
            setDeletingId(uri);
          },
        },
      ],
    ],
    [
      entityName,
      projectName,
      weave,
      history,
      makeBoardFromNode,
      navigateToExpression,
    ]
  );

  const sidebarActions = useMemo(
    () =>
      browserActions.map((actionSection, index) => {
        if (index === 0) {
          return actionSection.filter(
            action => action.label !== 'Table overview'
          );
        }
        return actionSection;
      }),
    [browserActions]
  );

  useEffect(() => {
    if (isLoading) {
      return;
    }
    if (params.preview) {
      const row = browserData.find(b => b._id === params.preview);
      if (!row) {
        setPreviewNode(undefined);
        return;
      }
      const expr = tableRowToNode(
        row.kind,
        params.entity!,
        params.project!,
        row._id
      );
      const node = (
        <HomePreviewSidebarTemplate
          title={row.name}
          row={row}
          setPreviewNode={setPreviewNode}
          actions={sidebarActions}
          emptyData={row['number of rows'] === 0}
          emptyDataMessage={<EmptyTableMessage />}>
          <SafeHomeExpressionPreviewParts
            expr={expr}
            navigateToExpression={navigateToExpression}
          />
        </HomePreviewSidebarTemplate>
      );
      setPreviewNode(node);
    } else {
      setPreviewNode(undefined);
    }
  }, [
    sidebarActions,
    browserData,
    history,
    params.entity,
    params.project,
    params.preview,
    setPreviewNode,
    navigateToExpression,
    isLoading,
  ]);

  return (
    <>
      <CenterBrowser
        allowSearch
        title={browserTitle}
        selectedRowId={params.preview}
        deletingId={deletingId}
        setDeletingId={setDeletingId}
        deleteTypeString="table"
        noDataCTA={`No Weave tables found for project: ${entityName}/${projectName}`}
        breadcrumbs={[
          {
            key: 'entity',
            text: entityName,
            onClick: () => {
              setPreviewNode(undefined);
              history.push(urlEntity(entityName));
            },
          },
          {
            key: 'project',
            text: projectName,
            onClick: () => {
              setPreviewNode(undefined);
              history.push(urlProject(entityName, projectName));
            },
          },
        ]}
        loading={isLoading}
        filters={{kind: {placeholder: 'All table kinds'}}}
        columns={[
          'name',
          'kind',
          'updated at',
          'created at',
          'created by',
          'number of rows',
        ]}
        data={browserData}
        actions={browserActions}
      />
    </>
  );
};

const EmptyTableMessageBlockContainer = styled(LayoutElements.HBlock)`
  background-color: ${globals.MOON_100};
  border-radius: 8px;
  width: 90%;
  margin-left: auto;
  margin-right: auto;
`;
EmptyTableMessageBlockContainer.displayName =
  'S.EmptyTableMessageBlockContainer';

const EmptyTableMessageIcon = styled.div`
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 15px;
`;
EmptyTableMessageIcon.displayName = 'S.EmptyTableMessageIcon';

const EmptyTableMessageText = styled.div`
  padding: 15px 20px 15px 0px;
  color: ${globals.MOON_600};
`;
EmptyTableMessageText.displayName = 'S.EmptyTableMessageText';

const EmptyTableMessage = () => {
  return (
    <div>
      <EmptyTableMessageBlockContainer>
        <EmptyTableMessageIcon>
          <IconLightbulbInfo style={{color: globals.MOON_600}} />
        </EmptyTableMessageIcon>
        <EmptyTableMessageText>
          <div style={{fontWeight: 600, marginBottom: '2px'}}>
            This table has no data
          </div>
          <div>
            Table preview and board creation are not available until data has
            been logged. Learn more about logging data to StreamTables{' '}
            <TargetBlank href="https://docs.wandb.ai/guides/weave/streamtable">
              here
            </TargetBlank>
            .
          </div>
        </EmptyTableMessageText>
      </EmptyTableMessageBlockContainer>
    </div>
  );
};
