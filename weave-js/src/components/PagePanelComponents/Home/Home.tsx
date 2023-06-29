import React, {FC, memo, useMemo, useState} from 'react';

import styled from 'styled-components';
import {ChildPanelFullConfig} from '../../Panel2/ChildPanel';
import {
  IconDashboardBlackboard,
  IconLaptopLocalComputer,
  IconTable,
  IconUserProfilePersonal,
  IconUsersTeam,
  IconWandb,
} from '../../Panel2/Icons';
import {useConfig} from '../../Panel2/panel';
import * as query from './query';
import * as LayoutElements from './LayoutElements';
import {CenterEntityBrowser} from './HomeCenterEntityBrowser';
import {LeftNav} from './HomeLeftNav';
import {HomeTopBar} from './HomeTopBar';

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
        <HomeTopBar
          inJupyter={props.inJupyter}
          updateConfig={props.updateConfig}
        />
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

export const Home = memo(HomeComp);
