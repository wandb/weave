import React, {
  FC,
  memo,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import styled from 'styled-components';
import {ChildPanelFullConfig} from '../../Panel2/ChildPanel';
import {
  IconDashboardBlackboard,
  IconLaptopLocalComputer,
  IconTable,
  IconUserProfilePersonal,
  IconUsersTeam,
} from '../../Panel2/Icons';
import * as query from './query';
import * as LayoutElements from './LayoutElements';
import {CenterEntityBrowser} from './HomeCenterEntityBrowser';
import {LeftNav} from './HomeLeftNav';
import {HomeTopBar} from './HomeTopBar';
import {NavigateToExpressionType} from './common';
import {isServedLocally, useIsAuthenticated} from '../util';

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

// Home Page TODO: Enable browsing recent assets
const RECENTS_SUPPORTED = false;

const HomeComp: FC<HomeProps> = props => {
  const navigateToExpression: NavigateToExpressionType = useCallback(
    newDashExpr => {
      props.updateConfig({
        vars: {},
        input_node: newDashExpr,
        id: '',
        config: undefined,
      });
    },
    [props]
  );
  const isLocallyServed = isServedLocally();
  const isAuthenticated = useIsAuthenticated();
  const userEntities = query.useUserEntities(isAuthenticated);
  const userName = query.useUserName(isAuthenticated);
  const [activeBrowserRoot, setActiveBrowserRoot] = useState<
    | undefined
    | {
        browserType: 'recent' | 'wandb' | 'drafts';
        rootId: string;
      }
  >(undefined);
  const recentSection = useMemo(() => {
    if (RECENTS_SUPPORTED) {
      return [
        {
          title: `Recent`,
          items: [
            {
              icon: IconDashboardBlackboard,
              label: `Boards`,
              active:
                activeBrowserRoot?.browserType === 'recent' &&
                activeBrowserRoot?.rootId === 'boards',
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
                activeBrowserRoot?.browserType === 'recent' &&
                activeBrowserRoot?.rootId === 'tables',
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
    } else {
      return [];
    }
  }, [activeBrowserRoot?.browserType, activeBrowserRoot?.rootId]);
  // }, []);

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
                  activeBrowserRoot?.browserType === 'wandb' &&
                  activeBrowserRoot?.rootId === entity,
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
    activeBrowserRoot?.browserType,
    activeBrowserRoot?.rootId,
    userEntities.result,
    userName.result,
  ]);

  const draftsSection = useMemo(() => {
    return [
      {
        title: `Drafts`,
        items: [
          // Home Page TODO: Enable browsing assets in draft state on remote server
          // {
          //   icon: IconWandb,
          //   label: `W&B hosted workspace`,
          //   active:
          //     activeBrowserRoot?.browserType === 'drafts' &&
          //     activeBrowserRoot?.rootId === 'wb_hosted',
          //   onClick: () => {
          //     setActiveBrowserRoot({
          //       browserType: 'drafts',
          //       rootId: 'wb_hosted',
          //     });
          //   },
          // },
          {
            icon: IconLaptopLocalComputer,
            label: `On this machine`,
            active:
              activeBrowserRoot?.browserType === 'drafts' &&
              activeBrowserRoot?.rootId === 'local',
            onClick: () => {
              setActiveBrowserRoot({
                browserType: 'drafts',
                rootId: 'local',
              });
            },
          },
        ],
      },
    ];
  }, [activeBrowserRoot?.browserType, activeBrowserRoot?.rootId]);

  const navSections = useMemo(() => {
    return [...recentSection, ...wandbSection, ...draftsSection];
  }, [draftsSection, recentSection, wandbSection]);

  const [previewNode, setPreviewNode] = useState<React.ReactNode>();

  useEffect(() => {
    // Create default root.
    const loading = userName.loading || isAuthenticated === undefined;
    if (!loading && activeBrowserRoot == null) {
      // If we have Recent enabled, go for that!
      if (RECENTS_SUPPORTED) {
        setActiveBrowserRoot({
          browserType: 'recent',
          rootId: 'boards',
        });
        // Next, if we are authenticated (we are always authed in the cloud)
      } else if (isAuthenticated && userName.result != null) {
        // It would be super cool to go straight to the first project that has weave objects
        setActiveBrowserRoot({
          browserType: 'wandb',
          rootId: userName.result,
        });
      } else if (isLocallyServed) {
        setActiveBrowserRoot({
          browserType: 'drafts',
          rootId: 'local',
        });
      } else {
        // This should never happen
        console.warn('Unable to determine root');
      }
    }
  }, [
    activeBrowserRoot,
    isAuthenticated,
    isLocallyServed,
    userName.loading,
    userName.result,
  ]);

  return (
    <LayoutElements.VStack>
      <LayoutElements.Block>
        <HomeTopBar
          inJupyter={props.inJupyter}
          navigateToExpression={navigateToExpression}
        />
      </LayoutElements.Block>
      {/* Main Region */}
      <LayoutElements.HSpace>
        {/* Left Bar */}
        <LeftNav sections={navSections} />
        {/* Center Content */}
        <CenterSpace>
          {activeBrowserRoot?.browserType === 'recent' ? (
            <>RECENT</>
          ) : activeBrowserRoot?.browserType === 'wandb' ? (
            <CenterEntityBrowser
              navigateToExpression={navigateToExpression}
              setPreviewNode={setPreviewNode}
              entityName={activeBrowserRoot?.rootId}
            />
          ) : activeBrowserRoot?.browserType === 'drafts' ? (
            <>DRAFTS</>
          ) : (
            <>Invalid Selection</>
          )}
        </CenterSpace>
        {/* Right Bar */}
        <LayoutElements.Block
          style={{
            width: previewNode != null ? '300px' : '0px',
          }}>
          {previewNode}
        </LayoutElements.Block>
      </LayoutElements.HSpace>
    </LayoutElements.VStack>
  );
};

export const Home = memo(HomeComp);
