import {opGet, constString} from '@wandb/weave/core';
import React, {useMemo, useState} from 'react';
import {IconInfo, IconOpenNewTab} from '../../Panel2/Icons';
import {CenterBrowserActionType, CenterBrowser} from './HomeCenterBrowser';
import {SetPreviewNodeType, NavigateToExpressionType} from './common';
import * as query from './query';
import {HomeBoardPreview} from './HomePreviewSidebar';
import moment from 'moment';

type CenterLocalBrowserPropsType = {
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
};

const rowToExpression = (row: any) => {
  const uri = `local-artifact:///${row.name}:${row['latest version id']}/obj`;
  return opGet({uri: constString(uri)});
};

// Just doing local boards for now!
export const CenterLocalBrowser: React.FC<
  CenterLocalBrowserPropsType
> = props => {
  const localDashboards = query.useLocalDashboards();
  const [selectedRowId, setSelectedRowId] = useState<string | undefined>();

  const browserData = useMemo(() => {
    return localDashboards.result
      .sort(a => -a.createdAt)
      .map(b => ({
        _id: b.name,
        name: b.name,
        'latest version id': b.version,
        // Note: even though this is `createdAt`, it is interpreted by the user
        // as `updatedAt` since it is the `created at` date for the latest
        // version.
        // TODO: Why is this date not utc??? Seems like a bug in the artifact writing code?
        'updated at': moment(b.createdAt).calendar(),
      }));
  }, [localDashboards]);

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
            const expr = rowToExpression(row);
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
            props.navigateToExpression(rowToExpression(row));
          },
        },
      ],
    ];
  }, [props]);

  return (
    <CenterBrowser
      allowSearch
      title={'Local Boards'}
      selectedRowId={selectedRowId}
      noDataCTA={`No Local Weave boards found.`}
      loading={localDashboards.loading}
      columns={['name', 'latest version id', 'updated at']}
      data={browserData}
      actions={browserActions}
    />
  );
};
