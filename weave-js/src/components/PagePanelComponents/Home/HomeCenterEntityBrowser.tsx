import React, {useMemo, useState} from 'react';

import {IconDown, IconInfo, IconOpenNewTab} from '../../Panel2/Icons';
import * as query from './query';
import {CenterBrowser, CenterBrowserActionType} from './HomeCenterBrowser';
import {useResettingState} from '@wandb/weave/common/util/hooks';
import moment from 'moment';
import {
  Node,
  constString,
  opArtifactMembershipArtifactVersion,
  opArtifactMembershipForAlias,
  opArtifactVersionDefaultFile,
  opArtifactVersionFile,
  opFileTable,
  opGet,
  opProjectArtifact,
  opRootProject,
  opTableRows,
} from '@wandb/weave/core';
import {NavigateToExpressionType, SetPreviewNodeType} from './common';

type CenterEntityBrowserPropsType = {
  entityName: string;
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
};

export const CenterEntityBrowser: React.FC<
  CenterEntityBrowserPropsType
> = props => {
  const [selectedProjectName, setSelectedProjectName] = useResettingState<
    string | undefined
  >(undefined, [props]);
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
  const projectNames = query.useProjectsForEntityWithWeaveObject(
    props.entityName
  );

  const browserData = useMemo(() => {
    return projectNames.result.map(projectName => ({
      _id: projectName,
      project: projectName,
      // TODO: get these from the server
      // runs: 20,
      // tables: 10,
      // dashboards: 5,
      // 'last edited': 'yesterday',
    }));
  }, [projectNames.result]);

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

  const loading = projectNames.loading;

  return (
    <CenterBrowser
      allowSearch
      columns={['project']}
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
  const [selectedAssetType, setSelectedAssetType] = useState<
    string | undefined
  >();
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
  const browserTitle = props.entityName + '/' + props.projectName;
  const browserData = [
    {
      _id: 'boards',
      'asset type': 'Boards',
      // TODO: get these from the server
      // 'count': 5,
      // 'last edited': 'yesterday',
    },
    {
      _id: 'tables',
      'asset type': 'Tables',
      // TODO: get these from the server
      // 'count': 5,
      // 'last edited': 'yesterday',
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
      data={browserData}
      actions={browserActions}
    />
  );
};

const CenterProjectBoardsBrowser: React.FC<
  CenterProjectBrowserInnerPropsType
> = props => {
  const browserTitle = props.entityName + '/' + props.projectName + '/Boards';

  const boards = query.useProjectBoards(props.entityName, props.projectName);
  const browserData = useMemo(() => {
    return boards.result.map(b => ({
      _id: b.name,
      name: b.name,
      'updated at': moment.utc(b.updatedAt).calendar(),
      'created at': moment.utc(b.createdAt).calendar(),
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
          label: 'Board details ',
          onClick: row => {
            props.setPreviewNode(<>HI MOM</>);
          },
        },
        {
          icon: IconOpenNewTab,
          label: 'Open Board',
          onClick: row => {
            const uri = `wandb-artifact:///${props.entityName}/${props.projectName}/${row._id}:latest/obj`;
            const newExpr = opGet({uri: constString(uri)});
            props.navigateToExpression(newExpr);
          },
        },
      ],
    ];
  }, [props]);

  return (
    <CenterBrowser
      allowSearch
      title={browserTitle}
      loading={boards.loading}
      columns={['name', 'updated at', 'created at', 'created by']}
      data={browserData}
      actions={browserActions}
    />
  );
};

const CenterProjectTablesBrowser: React.FC<
  CenterProjectBrowserInnerPropsType
> = props => {
  const browserTitle = props.entityName + '/' + props.projectName + '/Tables';

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
      kind: 'Run Stream',
      'updated at': moment.utc(b.updatedAt).calendar(),
      'created at': moment.utc(b.createdAt).calendar(),
      'created by': b.createdByUserName,
    }));
    const logged = loggedTables.result.map(b => ({
      _id: b.name,
      _updatedAt: b.updatedAt,
      name: b.name,
      kind: 'Logged Table',
      'updated at': moment.utc(b.updatedAt).calendar(),
      'created at': moment.utc(b.createdAt).calendar(),
      'created by': b.createdByUserName,
    }));
    const combined = [...streams, ...logged];
    combined.sort((a, b) => b._updatedAt - a._updatedAt);
    return combined;
  }, [isLoading, loggedTables.result, runStreams.result]);

  const browserActions: Array<
    CenterBrowserActionType<(typeof browserData)[number]>
  > = useMemo(() => {
    return [
      [
        // Home Page TODO: Enable awesome previews
        // {
        //   icon: IconInfo,
        //   label: 'Board details ',
        //   onClick: row => {
        //     props.setPreviewNode(<>HI MOM</>);
        //   },
        // },
        {
          icon: IconOpenNewTab,
          label: 'Open Table',
          onClick: row => {
            let newExpr: Node;
            if (row.kind === 'Run Stream') {
              const uri = `wandb-artifact:///${props.entityName}/${props.projectName}/${row._id}:latest/obj`;
              newExpr = opGet({uri: constString(uri)});
            } else {
              // This is a  hacky here. Would be nice to have better mapping
              const artName = row._id;
              const artNameParts = artName.split('-', 3);
              const tableName =
                artNameParts[artNameParts.length - 1] + '.table.json';
              newExpr = opTableRows({
                table: opFileTable({
                  file: opArtifactVersionFile({
                    artifactVersion: opArtifactMembershipArtifactVersion({
                      artifactMembership: opArtifactMembershipForAlias({
                        artifact: opProjectArtifact({
                          project: opRootProject({
                            entityName: constString(props.entityName),
                            projectName: constString(props.projectName),
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
            props.navigateToExpression(newExpr);
          },
        },
      ],
    ];
  }, [props]);

  return (
    <CenterBrowser
      allowSearch
      title={browserTitle}
      loading={isLoading}
      filters={{kind: {placeholder: 'All table kinds'}}}
      columns={['name', 'kind', 'updated at', 'created at', 'created by']}
      data={browserData}
      actions={browserActions}
    />
  );
};
