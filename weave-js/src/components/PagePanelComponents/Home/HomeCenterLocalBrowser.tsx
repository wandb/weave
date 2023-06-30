import {opGet, constString} from '@wandb/weave/core';
import {useMemo} from 'react';
import {IconInfo, IconOpenNewTab} from '../../Panel2/Icons';
import {CenterBrowserActionType, CenterBrowser} from './HomeCenterBrowser';
import {SetPreviewNodeType, NavigateToExpressionType} from './common';
import * as query from './query';
import {ChildPanel} from '../../Panel2/ChildPanel';
import {PreviewNode} from './PreviewNode';
import {HomePreviewSidebarTemplate} from './HomePreviewSidebar';

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

  const browserData = useMemo(() => {
    return localDashboards.result.map(b => ({
      _id: b.name,
      name: b.name,
      'latest version id': b.version,
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
            const expr = rowToExpression(row);
            const node = (
              <HomePreviewSidebarTemplate
                title={row.name}
                setPreviewNode={props.setPreviewNode}
                primaryAction={{
                  icon: IconOpenNewTab,
                  label: 'Open Board',
                  onClick: () => {
                    props.navigateToExpression(expr);
                  },
                }}>
                <PreviewNode inputNode={expr} />
              </HomePreviewSidebarTemplate>
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
      loading={localDashboards.loading}
      columns={['name', 'latest version id']}
      data={browserData}
      actions={browserActions}
    />
  );
};
