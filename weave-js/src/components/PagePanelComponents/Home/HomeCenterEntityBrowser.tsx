import React, {useEffect, useMemo, useState} from 'react';

import {
  IconCopy,
  IconChevronDown,
  IconInfo,
  IconOpenNewTab,
  IconDelete,
  IconFullScreenModeExpand,
  IconAddNew,
} from '@wandb/weave/components/Icon';
import * as query from './query';
import {CenterBrowser, CenterBrowserActionType} from './HomeCenterBrowser';
import moment from 'moment';
import {
  Node,
  callOpVeryUnsafe,
  constString,
  list,
  opArtifactVersionFile,
  opFileTable,
  opGet,
  opIsNone,
  opRootProject,
  opTableRows,
  typedDict,
} from '@wandb/weave/core';
import {NavigateToExpressionType, SetPreviewNodeType} from './common';
import {useNodeValue} from '@wandb/weave/react';
import {useWeaveContext} from '@wandb/weave/context';
import {
  HomePreviewSidebarTemplate,
  HomeExpressionPreviewParts,
  SEED_BOARD_OP_NAME,
} from './HomePreviewSidebar';
import {useHistory, useParams} from 'react-router-dom';
import {HomeParams} from './Home';
import {setDocumentTitle} from '@wandb/weave/util/document';
import {useMakeLocalBoardFromNode} from '../../Panel2/pyBoardGen';
import {
  urlEntity,
  urlProject,
  urlProjectAssetPreview,
  urlProjectAssets,
} from '../../../urls';

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
            // TODO: make this work for local. Probably need to bring over `urlPrefixed`
            const url = `https://wandb.ai/${props.entityName}/${row.project}/overview`;
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
      columns={['project', 'boards', 'tables', 'updated at']}
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
        _id: 'boards',
        'asset type': 'Boards',
        count: assetCounts.result.boardCount ?? 0,
      },
      {
        _id: 'tables',
        'asset type': 'Tables',
        count:
          (assetCounts.result.loggedTableCount ?? 0) +
          (assetCounts.result.runStreamCount ?? 0),
      },
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
            const assetType = row._id === 'boards' ? 'board' : 'table';
            history.push(
              urlProjectAssets(params.entity!, params.project!, assetType)
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
          <HomeExpressionPreviewParts
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
    newExpr = callOpVeryUnsafe(
      'stream_table-rows',
      {
        self: node,
      },
      list(typedDict({}))
    ) as any;
  } else {
    // This is a hack. Would be nice to have better mapping
    // Note that this will not work for tables with spaces in their name
    // as we strip the space out to make the artifact name.
    const artNameParts = artName.split('-', 3);
    const tableName = artNameParts[artNameParts.length - 1] + '.table.json';

    const uri = `wandb-artifact:///${entityName}/${projectName}/${artName}:latest`;
    newExpr = opTableRows({
      table: opFileTable({
        file: opArtifactVersionFile({
          artifactVersion: opGet({uri: constString(uri)}),
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
    }));
    const logged = loggedTables.result.map(b => ({
      _id: b.name,
      _updatedAt: b.updatedAt,
      name: b.name,
      kind: 'Logged Table',
      'updated at': moment.utc(b.updatedAt).local().calendar(),
      'created at': moment.utc(b.createdAt).local().calendar(),
      'created by': b.createdByUserName,
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
          onClick: row => {
            navigateToExpression(
              tableRowToNode(row.kind, entityName, projectName, row._id)
            );
          },
        },
        {
          icon: IconCopy,
          label: 'Copy Weave expression',
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
          actions={sidebarActions}>
          <HomeExpressionPreviewParts
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
        columns={['name', 'kind', 'updated at', 'created at', 'created by']}
        data={browserData}
        actions={browserActions}
      />
    </>
  );
};
