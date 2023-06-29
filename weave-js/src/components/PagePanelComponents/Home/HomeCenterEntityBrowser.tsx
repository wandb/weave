import React, {useMemo, useState} from 'react';

import {IconInfo, IconOpenNewTab} from '../../Panel2/Icons';
import * as query from './query';
import {CenterBrowser, CenterBrowserActionType} from './HomeCenterBrowser';

export const CenterEntityBrowser: React.FC<{
  entityName: string;
}> = props => {
  const browserTitle = props.entityName;
  const [selectedProjectName, setSelectedProjectName] = useState<
    string | undefined
  >();

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
          icon: IconInfo,
          label: 'Browse project',
          onClick: row => {
            setSelectedProjectName(row._id);
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
  }, [props.entityName]);

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
