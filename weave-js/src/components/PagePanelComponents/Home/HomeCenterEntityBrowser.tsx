import React, {useMemo, useState} from 'react';

import {IconDown, IconOpenNewTab} from '../../Panel2/Icons';
import * as query from './query';
import {CenterBrowser, CenterBrowserActionType} from './HomeCenterBrowser';
import {useResettingState} from '@wandb/weave/common/util/hooks';
import moment from 'moment';

export const CenterEntityBrowser: React.FC<{
  entityName: string;
}> = props => {
  const [selectedProjectName, setSelectedProjectName] = useResettingState<
    string | undefined
  >(undefined, [props]);
  if (selectedProjectName == null) {
    return (
      <CenterEntityBrowserInner
        entityName={props.entityName}
        setSelectedProjectName={setSelectedProjectName}
      />
    );
  } else {
    return (
      <CenterProjectBrowser
        entityName={props.entityName}
        projectName={selectedProjectName}
        setSelectedProjectName={setSelectedProjectName}
      />
    );
  }
};
export const CenterEntityBrowserInner: React.FC<{
  entityName: string;
  setSelectedProjectName: (name: string | undefined) => void;
}> = props => {
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

const CenterProjectBrowser: React.FC<{
  entityName: string;
  projectName: string;
  setSelectedProjectName: (name: string | undefined) => void;
}> = props => {
  const [selectedAssetType, setSelectedAssetType] = useState<
    string | undefined
  >();
  if (selectedAssetType == null) {
    return (
      <CenterProjectBrowserInner
        entityName={props.entityName}
        projectName={props.projectName}
        setSelectedProjectName={props.setSelectedProjectName}
        setSelectedAssetType={setSelectedAssetType}
      />
    );
  } else if (selectedAssetType === 'boards') {
    return (
      <CenterProjectBoardBrowser
        entityName={props.entityName}
        projectName={props.projectName}
        setSelectedProjectName={props.setSelectedProjectName}
        setSelectedAssetType={setSelectedAssetType}
      />
    );
  } else {
    return <>Not implemented</>;
  }
};

const CenterProjectBrowserInner: React.FC<{
  entityName: string;
  projectName: string;
  setSelectedProjectName: (name: string | undefined) => void;
  setSelectedAssetType: (name: string | undefined) => void;
}> = props => {
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

const CenterProjectBoardBrowser: React.FC<{
  entityName: string;
  projectName: string;
  setSelectedProjectName: (name: string | undefined) => void;
  setSelectedAssetType: (name: string | undefined) => void;
}> = props => {
  const browserTitle =
    props.entityName + '/' + props.projectName + '/' + 'Boards';

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
      loading={boards.loading}
      columns={['name', 'updated at', 'created at', 'created by']}
      data={browserData}
      actions={browserActions}
    />
  );
};
