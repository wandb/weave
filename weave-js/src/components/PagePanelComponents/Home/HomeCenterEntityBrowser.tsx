import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {
  IconAddNew,
  IconCopy,
  IconDown,
  IconInfo,
  IconOpenNewTab,
} from '../../Panel2/Icons';
import * as query from './query';
import {CenterBrowser, CenterBrowserActionType} from './HomeCenterBrowser';
import moment from 'moment';
import {
  Node,
  callOpVeryUnsafe,
  constString,
  list,
  opArtifactMembershipArtifactVersion,
  opArtifactMembershipForAlias,
  opArtifactVersionFile,
  opFileTable,
  opGet,
  opIsNone,
  opProjectArtifact,
  opRootProject,
  opTableRows,
  typedDict,
  varNode,
} from '@wandb/weave/core';
import {NavigateToExpressionType, SetPreviewNodeType} from './common';
import {useNodeValue} from '@wandb/weave/react';
import {useWeaveContext} from '@wandb/weave/context';
import {
  HomePreviewSidebarTemplate,
  HomeBoardPreview,
  HomeExpressionPreviewParts,
} from './HomePreviewSidebar';
import {useMakeLocalBoardFromNode} from '../../Panel2/pyBoardGen';
import WandbLoader from '@wandb/weave/common/components/WandbLoader';
import {IconMagicWandStar} from '../../Icon';
import {getFullChildPanel} from '../../Panel2/ChildPanel';
import {useNewDashFromItems} from '../../Panel2/PanelRootBrowser/util';

type CenterEntityBrowserPropsType = {
  entityName: string;
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
};

export const CenterEntityBrowser: React.FC<
  CenterEntityBrowserPropsType
> = props => {
  const [selectedProjectName, setSelectedProjectNameRaw] = useState<
    string | undefined
  >();

  const setSelectedProjectName = useCallback(
    (projectName?: string) => {
      setSelectedProjectNameRaw(projectName);
      props.setPreviewNode(undefined);
    },
    [props, setSelectedProjectNameRaw]
  );

  if (selectedProjectName == null) {
    return (
      <CenterEntityBrowserInner
        {...props}
        setSelectedProjectName={setSelectedProjectName}
      />
    );
  } else {
    return (
      <CenterProjectBrowser
        {...props}
        projectName={selectedProjectName}
        setSelectedProjectName={setSelectedProjectName}
      />
    );
  }
};

type CenterEntityBrowserInnerPropsType = CenterEntityBrowserPropsType & {
  setSelectedProjectName: (name: string | undefined) => void;
};

export const CenterEntityBrowserInner: React.FC<
  CenterEntityBrowserInnerPropsType
> = props => {
  const browserTitle = props.entityName;
  const projectsMeta = query.useProjectsForEntityWithWeaveObject(
    props.entityName
  );

  const browserData = useMemo(() => {
    // TODO: make sorting more customizable and awesome
    const sortedMeta = [...projectsMeta.result].sort(
      (a, b) => b.updatedAt - a.updatedAt
    );
    return sortedMeta.map(meta => ({
      _id: meta.name,
      project: meta.name,
      boards: (meta.num_boards ?? 0) > 0 ? meta.num_boards : null,
      tables:
        (meta.num_stream_tables + meta.num_logged_tables ?? 0) > 0
          ? meta.num_stream_tables + meta.num_logged_tables
          : null,
      'updated at': moment.utc(meta.updatedAt).local().calendar(),
    }));
  }, [projectsMeta.result]);

  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(() => {
    return [
      [
        {
          icon: IconDown,
          label: 'Browse project',
          onClick: row => {
            props.setSelectedProjectName(row._id);
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
  }, [props]);

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
  const [selectedAssetType, setSelectedAssetTypeRaw] = useState<
    string | undefined
  >();

  const setSelectedAssetType = useCallback(
    (projectName?: string) => {
      setSelectedAssetTypeRaw(projectName);
      props.setPreviewNode(undefined);
    },
    [props, setSelectedAssetTypeRaw]
  );

  const noAccessNode = opIsNone({
    val: opRootProject({
      entityName: constString(props.entityName),
      projectName: constString(props.projectName),
    }),
  });
  const noAccessValueNode = useNodeValue(noAccessNode);

  // This effect automatically kicks back to the root if the project is not
  // accessible - which occurs when you change states.
  useEffect(() => {
    if (!noAccessValueNode.loading && noAccessValueNode.result) {
      props.setSelectedProjectName(undefined);
    }
  }, [noAccessValueNode.loading, noAccessValueNode.result, props]);

  if (selectedAssetType == null) {
    return (
      <CenterProjectBrowserInner
        {...props}
        setSelectedAssetType={setSelectedAssetType}
      />
    );
  } else if (selectedAssetType === 'boards') {
    return (
      <CenterProjectBoardsBrowser
        {...props}
        setSelectedAssetType={setSelectedAssetType}
      />
    );
  } else if (selectedAssetType === 'tables') {
    return (
      <CenterProjectTablesBrowser
        {...props}
        setSelectedAssetType={setSelectedAssetType}
      />
    );
  } else {
    return <>Not implemented</>;
  }
};

type CenterProjectBrowserInnerPropsType = {
  entityName: string;
  projectName: string;
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
  setSelectedProjectName: (name: string | undefined) => void;
  setSelectedAssetType: (name: string | undefined) => void;
};

const CenterProjectBrowserInner: React.FC<
  CenterProjectBrowserInnerPropsType
> = props => {
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
          icon: IconDown,
          label: 'Browse asset type',
          onClick: row => {
            props.setSelectedAssetType(row._id);
          },
        },
      ],
    ];
  }, [props]);

  return (
    <CenterBrowser
      title={browserTitle}
      loading={assetCounts.loading}
      breadcrumbs={[
        {
          key: 'entity',
          text: props.entityName,
          onClick: () => {
            props.setSelectedProjectName(undefined);
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
> = props => {
  const browserTitle = 'Boards';
  const [selectedRowId, setSelectedRowId] = useState<string | undefined>();

  const boards = query.useProjectBoards(props.entityName, props.projectName);
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
          icon: IconInfo,
          label: 'Board details',
          onClick: row => {
            setSelectedRowId(row._id);
            const expr = rowToExpression(
              props.entityName,
              props.projectName,
              row._id
            );
            const node = (
              <HomeBoardPreview
                expr={expr}
                name={row.name}
                setPreviewNode={props.setPreviewNode}
                navigateToExpression={props.navigateToExpression}
              />
            );
            props.setPreviewNode(node);
          },
        },
      ],
      [
        {
          icon: IconOpenNewTab,
          label: 'Open Board',
          onClick: row => {
            props.navigateToExpression(
              rowToExpression(props.entityName, props.projectName, row._id)
            );
          },
        },
      ],
    ];
  }, [props, setSelectedRowId]);

  return (
    <CenterBrowser
      allowSearch
      title={browserTitle}
      selectedRowId={selectedRowId}
      noDataCTA={`No Weave boards found for project: ${props.entityName}/${props.projectName}`}
      breadcrumbs={[
        {
          key: 'entity',
          text: props.entityName,
          onClick: () => {
            props.setSelectedProjectName(undefined);
            props.setSelectedAssetType(undefined);
          },
        },
        {
          key: 'project',
          text: props.projectName,
          onClick: () => {
            props.setSelectedAssetType(undefined);
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
    // This is a  hacky here. Would be nice to have better mapping
    const artNameParts = artName.split('-', 3);
    const tableName = artNameParts[artNameParts.length - 1] + '.table.json';
    newExpr = opTableRows({
      table: opFileTable({
        file: opArtifactVersionFile({
          artifactVersion: opArtifactMembershipArtifactVersion({
            artifactMembership: opArtifactMembershipForAlias({
              artifact: opProjectArtifact({
                project: opRootProject({
                  entityName: constString(entityName),
                  projectName: constString(projectName),
                }),
                artifactName: constString(artName),
              }),
              aliasName: constString('latest'),
            }),
          }),
          path: constString(tableName),
        }),
      }),
    });
  }
  return newExpr;
};

const CenterProjectTablesBrowser: React.FC<
  CenterProjectBrowserInnerPropsType
> = props => {
  const weave = useWeaveContext();
  const browserTitle = 'Tables';
  const [selectedRowId, setSelectedRowId] = useState<string | undefined>();

  const runStreams = query.useProjectRunStreams(
    props.entityName,
    props.projectName
  );
  const loggedTables = query.useProjectRunLoggedTables(
    props.entityName,
    props.projectName
  );
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
      'updated at': moment.utc(b.updatedAt).local().calendar(),
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

  const [seedingBoard, setSeedingBoard] = useState(false);
  const makeNewDashboard = useNewDashFromItems();

  const makeBoardFromNode = useMakeLocalBoardFromNode();
  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(() => {
    return [
      [
        // Home Page TODO: Enable awesome previews
        {
          icon: IconInfo,
          label: 'Table details',
          onClick: row => {
            setSelectedRowId(row._id);
            const expr = tableRowToNode(
              row.kind,
              props.entityName,
              props.projectName,
              row._id
            );
            const node = (
              <HomePreviewSidebarTemplate
                title={row.name}
                setPreviewNode={props.setPreviewNode}
                // TODO: These actions are literally copy/paste from below - rework this pattern to be more generic
                primaryAction={{
                  icon: IconAddNew,
                  label: 'Seed new board',
                  onClick: () => {
                    const name =
                      'dashboard-' + moment().format('YY_MM_DD_hh_mm_ss');
                    makeNewDashboard(
                      name,
                      {panel0: getFullChildPanel(varNode(expr.type, 'var0'))},
                      {var0: expr},
                      newDashExpr => {
                        props.navigateToExpression(newDashExpr);
                      }
                    );
                  },
                }}
                secondaryAction={{
                  icon: IconOpenNewTab,
                  label: 'Open Table',
                  onClick: () => {
                    props.navigateToExpression(expr);
                  },
                }}>
                <HomeExpressionPreviewParts expr={expr} />
              </HomePreviewSidebarTemplate>
            );
            props.setPreviewNode(node);
          },
        },
      ],
      [
        {
          icon: IconAddNew,
          label: 'Seed new board',
          onClick: row => {
            const node = tableRowToNode(
              row.kind,
              props.entityName,
              props.projectName,
              row._id
            );
            setSeedingBoard(true);
            makeBoardFromNode('py_board-seed_board', node, newDashExpr => {
              setSeedingBoard(false);
              props.navigateToExpression(newDashExpr);
            });
          },
        },
        {
          icon: IconMagicWandStar,
          label: 'Seed auto board',
          onClick: row => {
            const node = tableRowToNode(
              row.kind,
              props.entityName,
              props.projectName,
              row._id
            );
            setSeedingBoard(true);
            makeBoardFromNode('py_board-seed_autoboard', node, newDashExpr => {
              setSeedingBoard(false);
              props.navigateToExpression(newDashExpr);
            });
          },
        },
        {
          icon: IconOpenNewTab,
          label: 'Open Table',
          onClick: row => {
            props.navigateToExpression(
              tableRowToNode(
                row.kind,
                props.entityName,
                props.projectName,
                row._id
              )
            );
          },
        },
      ],
      [
        {
          icon: IconCopy,
          label: 'Copy Weave expression',
          onClick: row => {
            const node = tableRowToNode(
              row.kind,
              props.entityName,
              props.projectName,
              row._id
            );
            const copyText = weave.expToString(node);
            navigator.clipboard.writeText(copyText).then(() => {
              // give user feedback
            });
          },
        },
      ],
    ];
  }, [makeBoardFromNode, makeNewDashboard, props, weave]);

  return (
    <>
      {seedingBoard && <WandbLoader />}
      <CenterBrowser
        allowSearch
        title={browserTitle}
        selectedRowId={selectedRowId}
        noDataCTA={`No Weave tables found for project: ${props.entityName}/${props.projectName}`}
        breadcrumbs={[
          {
            key: 'entity',
            text: props.entityName,
            onClick: () => {
              props.setSelectedProjectName(undefined);
              props.setSelectedAssetType(undefined);
            },
          },
          {
            key: 'project',
            text: props.projectName,
            onClick: () => {
              props.setSelectedAssetType(undefined);
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
