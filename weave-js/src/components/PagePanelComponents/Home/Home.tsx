import {voidNode} from '@wandb/weave/core';
import moment from 'moment';
import React, {FC, memo, useCallback, useMemo, useState} from 'react';
import getConfig from '../../../config';

import styled from 'styled-components';
import {WBButton} from '../../../common/components/elements/WBButtonNew';
import {useWeaveContext} from '../../../context';
import {ChildPanelFullConfig} from '../../Panel2/ChildPanel';
import {
  IconAddNew as IconAddNewUnstyled,
  IconDashboardBlackboard,
  IconLaptopLocalComputer,
  IconTable,
  IconUserProfilePersonal,
  IconUsersTeam,
  IconWandb,
  IconWeaveLogo,
} from '../../Panel2/Icons';
import {useNewPanelFromRootQueryCallback} from '../../Panel2/PanelRootBrowser/util';
import {useConfig} from '../../Panel2/panel';
import * as query from './query';
import * as LayoutElements from './LayoutElements';
import {CenterEntityBrowser} from './HomeCenterEntityBrowser';
import {LeftNav} from './HomeLeftNav';

const CenterSpace = styled(LayoutElements.VSpace)`
  border: 1px solid #dadee3;
  box-shadow: 0px 8px 16px 0px #0e10140a;
  border-top-right-radius: 12px;
  border-top-left-radius: 12px;
  margin-right: 12px;
`;

type HomeProps = {
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  inJupyter: boolean;
};

const HomeComp: FC<HomeProps> = props => {
  const now = moment().format('YY_MM_DD_hh_mm_ss');
  const inJupyter = props.inJupyter;
  const defaultName = now;
  const [newName] = useState('');
  const weave = useWeaveContext();
  const name = 'dashboard-' + (newName === '' ? defaultName : newName);
  const makeNewDashboard = useNewPanelFromRootQueryCallback();
  const {urlPrefixed} = getConfig();
  const newDashboard = useCallback(() => {
    makeNewDashboard(name, voidNode(), true, newDashExpr => {
      if (inJupyter) {
        const expStr = weave
          .expToString(newDashExpr)
          .replace(/\n+/g, '')
          .replace(/\s+/g, '');
        window.open(
          urlPrefixed(`?exp=${encodeURIComponent(expStr)}`),
          '_blank'
        );
      } else {
        props.updateConfig({
          vars: {},
          input_node: newDashExpr,
          id: '',
          config: undefined,
        });
      }
    });
  }, [inJupyter, makeNewDashboard, name, props, urlPrefixed, weave]);
  const [rootConfig, updateRootConfig] = useConfig();

  const [activeBrowserRoot, setActiveBrowserRoot] = useState<{
    browserType: 'recent' | 'wandb' | 'drafts';
    rootId: string;
  }>({
    browserType: 'recent',
    rootId: 'boards',
  });

  const userEntities = query.useUserEntities();
  const userName = query.useUserName();

  const recentSection = useMemo(() => {
    return [
      {
        title: `Recent`,
        items: [
          {
            icon: IconDashboardBlackboard,
            label: `Boards`,
            active:
              activeBrowserRoot.browserType === 'recent' &&
              activeBrowserRoot.rootId === 'boards',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'recent',
                rootId: 'boards',
              });
            },
          },
          {
            icon: IconTable,
            label: `Tables`,
            active:
              activeBrowserRoot.browserType === 'recent' &&
              activeBrowserRoot.rootId === 'tables',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'recent',
                rootId: 'tables',
              });
            },
          },
        ],
      },
    ];
  }, [activeBrowserRoot.browserType, activeBrowserRoot.rootId]);

  const wandbSection = useMemo(() => {
    return userEntities.result.length === 0
      ? ([] as any)
      : [
          {
            title: `Weights & Biases`,
            items: userEntities.result
              .sort((a, b) => {
                if (a === userName.result) {
                  return -1;
                }
                if (b === userName.result) {
                  return 1;
                }
                if (a < b) {
                  return -1;
                }
                if (a > b) {
                  return 1;
                }
                return 0;
              })
              .map(entity => ({
                icon:
                  entity === userName.result
                    ? IconUserProfilePersonal
                    : IconUsersTeam,
                label: entity,
                active:
                  activeBrowserRoot.browserType === 'wandb' &&
                  activeBrowserRoot.rootId === entity,
                onClick: () => {
                  setActiveBrowserRoot({
                    browserType: 'wandb',
                    rootId: entity,
                  });
                },
              })),
          },
        ];
  }, [
    activeBrowserRoot.browserType,
    activeBrowserRoot.rootId,
    userEntities.result,
    userName.result,
  ]);

  const draftsSection = useMemo(() => {
    return [
      {
        title: `Drafts`,
        items: [
          {
            icon: IconWandb,
            label: `W&B hosted workspace`,
            active:
              activeBrowserRoot.browserType === 'drafts' &&
              activeBrowserRoot.rootId === 'wb_hosted',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'wandb',
                rootId: 'wb_hosted',
              });
            },
          },
          {
            icon: IconLaptopLocalComputer,
            label: `On this machine`,
            active:
              activeBrowserRoot.browserType === 'drafts' &&
              activeBrowserRoot.rootId === 'local',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'wandb',
                rootId: 'local',
              });
            },
          },
        ],
      },
    ];
  }, [activeBrowserRoot.browserType, activeBrowserRoot.rootId]);

  const navSections = useMemo(() => {
    return [...recentSection, ...wandbSection, ...draftsSection];
  }, [draftsSection, recentSection, wandbSection]);

  const [previewNode, setPreviewNode] = useState<any>(undefined);

  return (
    <LayoutElements.VStack>
      <LayoutElements.Block>
        <TopBar>
          <TopBarLeft>
            <WeaveLogo />
            Weave
          </TopBarLeft>
          <TopBarRight>
            <WBButton variant={`confirm`} onClick={newDashboard}>
              <IconAddNew />
              New board
            </WBButton>
          </TopBarRight>
        </TopBar>
      </LayoutElements.Block>
      {/* Main Region */}
      <LayoutElements.HSpace>
        {/* Left Bar */}
        <LeftNav sections={navSections} />
        {/* Center Content */}
        <CenterSpace>
          {activeBrowserRoot.browserType === 'recent' ? (
            <>RECENT</>
          ) : activeBrowserRoot.browserType === 'wandb' ? (
            <CenterEntityBrowser entityName={activeBrowserRoot.rootId} />
          ) : activeBrowserRoot.browserType === 'drafts' ? (
            <>DRAFTS</>
          ) : (
            <>Invalid Selection</>
          )}
        </CenterSpace>
        {/* Right Bar */}
        {previewNode != null && (
          <LayoutElements.Block>
            <div
              style={{
                width: '300px',
              }}>
              c
            </div>
          </LayoutElements.Block>
        )}
      </LayoutElements.HSpace>
    </LayoutElements.VStack>
  );
};

// const browserFilters = [
//   {
//     placeholder: 'All entities',
//     options: [
//       {key: 1, text: 'Choice 1', value: 1},
//       {key: 2, text: 'Choice 2', value: 2},
//       {key: 3, text: 'Choice 3', value: 3},
//     ],
//     onChange: () => {},
//   },
//   {
//     placeholder: 'All projects',
//     options: [
//       {key: 1, text: 'Choice 1', value: 1},
//       {key: 2, text: 'Choice 2', value: 2},
//       {key: 3, text: 'Choice 3', value: 3},
//     ],
//     onChange: () => {},
//   },
// ];

// const browserData: Array<CenterBrowserDataType> = [
//   {
//     _id: 0,
//     Board: 'Board 1',
//     Entity: 'timssweeney',
//     Project: 'weave',
//     'Last modified': '2 days ago',
//   },
//   {
//     _id: 1,
//     Board: 'Board 2',
//     Entity: 'timssweeney',
//     Project: 'weave',
//     'Last modified': 'June 21, 2023',
//   },
// ];
// const browserActions: Array<CenterBrowserActionType> = [
//   [
//     {
//       icon: IconInfo,
//       label: 'Object details',
//       onClick: (row: CenterBrowserDataType, index: number) => {
//         console.log('DETAILS', row, index);
//       },
//     },
//     {
//       icon: IconAddNew,
//       label: 'Seed new board',
//       onClick: (row: CenterBrowserDataType, index: number) => {
//         console.log('SEED', row, index);
//       },
//     },
//   ],
//   [
//     {
//       icon: IconCopy,
//       label: 'Copy Weave expression',
//       onClick: (row: CenterBrowserDataType, index: number) => {
//         console.log('COPY', row, index);
//       },
//     },
//   ],
// ];

export const Home = memo(HomeComp);

const TopBar = styled.div`
  height: 64px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const TopBarLeft = styled.div`
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: 600;
`;

const TopBarRight = styled.div`
  display: flex;
  align-items: center;
`;

const WeaveLogo = styled(IconWeaveLogo)`
  width: 32px;
  height: 32px;
  margin-right: 12px;
`;

const IconAddNew = styled(IconAddNewUnstyled)`
  width: 18px;
  height: 18px;
  margin-right: 6px;
`;
