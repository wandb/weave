import React, {useMemo, useState} from 'react';

import {IconDown, IconInfo, IconOpenNewTab} from '../../Panel2/Icons';
import * as query from './query';
import {CenterBrowser, CenterBrowserActionType} from './HomeCenterBrowser';
import {useResettingState} from '@wandb/weave/common/util/hooks';
import moment from 'moment';
import {constString, opGet} from '@wandb/weave/core';
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
      <CenterProjectBoardBrowser
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

const CenterProjectBoardBrowser: React.FC<
  CenterProjectBrowserInnerPropsType
> = props => {
  const browserTitle = props.entityName + '/' + props.projectName + '/Boards';

  const boards = query.useProjectBoards(props.entityName, props.projectName);
  const browserData = useMemo(() => {
    return boards.result.map(b => ({
      _id: b.name,
      name: b.name,
      'updated at': moment(b.updatedAt).calendar(),
      'created at': moment(b.createdAt).calendar(),
      'created by': b.createdByUserName,
    }));
  }, [boards]);

  // Next up: preview board and edit board

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
      title={browserTitle}
      loading={boards.loading}
      columns={['name', 'updated at', 'created at', 'created by']}
      data={browserData}
      actions={browserActions}
    />
  );
};
