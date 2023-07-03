import {opGet, constString} from '@wandb/weave/core';
import {useMemo} from 'react';
import {IconInfo, IconOpenNewTab, IconWeaveLogoGray} from '../../Panel2/Icons';
import {CenterBrowserActionType, CenterBrowser} from './HomeCenterBrowser';
import {SetPreviewNodeType, NavigateToExpressionType} from './common';
import * as query from './query';
import {HomeBoardPreview} from './HomePreviewSidebar';
import {HBlock, VStack} from './LayoutElements';

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
              <HomeBoardPreview
                expr={expr}
                name={row.name}
                setPreviewNode={props.setPreviewNode}
                navigateToExpression={props.navigateToExpression}
              />
              // <HomePreviewSidebarTemplate
              //   title={row.name}
              //   setPreviewNode={props.setPreviewNode}
              //   primaryAction={{
              //     icon: IconOpenNewTab,
              //     label: 'Open Board',
              //     onClick: () => {
              //       props.navigateToExpression(expr);
              //     },
              //   }}>
              //   <VStack style={{gap: '16px'}}>
              //     <VBlock style={{gap: '8px'}}>
              //       <span style={{color: '#2B3038', fontWeight: 600}}>
              //         Preview
              //       </span>
              //       <Block>
              //         <PreviewNode key={key} inputNode={expr} />
              //       </Block>
              //     </VBlock>
              //     <VBlock style={{gap: '8px'}}>
              //       <span style={{color: '#2B3038', fontWeight: 600}}>
              //         Expression
              //       </span>
              //       <Block>
              //         {/* <Unclickable style={{}}> */}
              //         <WeaveExpression
              //           expr={expr}
              //           onMount={() => {}}
              //           onFocus={() => {}}
              //           onBlur={() => {}}
              //           frozen
              //         />
              //         {/* </Unclickable> */}
              //       </Block>
              //     </VBlock>
              //   </VStack>
              // </HomePreviewSidebarTemplate>
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
      noDataCTA={`No Local Weave boards found.`}
      loading={localDashboards.loading}
      columns={['name', 'latest version id']}
      data={browserData}
      actions={browserActions}
    />
  );
};
