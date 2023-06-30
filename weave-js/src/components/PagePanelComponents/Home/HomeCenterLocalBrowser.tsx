import {opGet, constString} from '@wandb/weave/core';
import {useMemo} from 'react';
import {IconInfo, IconOpenNewTab} from '../../Panel2/Icons';
import {CenterBrowserActionType, CenterBrowser} from './HomeCenterBrowser';
import {SetPreviewNodeType, NavigateToExpressionType} from './common';
import * as query from './query';

type CenterLocalBrowserPropsType = {
  setPreviewNode: SetPreviewNodeType;
  navigateToExpression: NavigateToExpressionType;
};

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
          label: 'Board details ',
          onClick: row => {
            props.setPreviewNode(<>HI MOM</>);
          },
        },
      ],
      [
        {
          icon: IconOpenNewTab,
          label: 'Open Board',
          onClick: row => {
            const uri = `local-artifact:///${row.name}:${row['latest version id']}/obj`;
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
      title={'Local Boards'}
      loading={localDashboards.loading}
      columns={['name', 'latest version id']}
      data={browserData}
      actions={browserActions}
    />
  );
};
