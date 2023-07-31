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
  IconWeaveLogo,
} from '../../Panel2/Icons';
import * as query from './query';
import * as LayoutElements from './LayoutElements';
import {CenterEntityBrowser} from './HomeCenterEntityBrowser';
import {LeftNav} from './HomeLeftNav';
import {HomeTopBar} from './HomeTopBar';
import {NavigateToExpressionType} from './common';
import {isServedLocally, useIsAuthenticated} from '../util';
import {CenterLocalBrowser} from './HomeCenterLocalBrowser';
import {MOON_250} from '@wandb/weave/common/css/color.styles';

const CenterSpace = styled(LayoutElements.VSpace)`
  border: 1px solid ${MOON_250};
  box-shadow: 0px 8px 16px 0px #0e10140a;
  border-top-right-radius: 12px;
  border-top-left-radius: 12px;
`;

type HomeProps = {
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  inJupyter: boolean;
};

// Home Page TODO: Enable browsing recent assets
const RECENTS_SUPPORTED = false;

const HomeComp: FC<HomeProps> = props => {
  const [previewNode, setPreviewNode] = useState<React.ReactNode>();
  const navigateToExpression: NavigateToExpressionType = useCallback(
    newDashExpr => {
      setPreviewNode(undefined);
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
                setPreviewNode(undefined);
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
                setPreviewNode(undefined);
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
                  setPreviewNode(undefined);
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
    if (!isLocallyServed) {
      return [];
    }
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
              setPreviewNode(undefined);
            },
          },
        ],
      },
    ];
  }, [
    activeBrowserRoot?.browserType,
    activeBrowserRoot?.rootId,
    isLocallyServed,
  ]);

  const navSections = useMemo(() => {
    return [...recentSection, ...wandbSection, ...draftsSection];
  }, [draftsSection, recentSection, wandbSection]);

  const loading = userName.loading || isAuthenticated === undefined;
  useEffect(() => {
    // Create default root.
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
    loading,
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
      <LayoutElements.HSpace
        style={{
          gap: '12px',
        }}>
        {/* Left Bar */}
        <LeftNav sections={navSections} />
        {/* Center Content */}
        {!loading && (
          <CenterSpace>
            {activeBrowserRoot?.browserType === 'recent' ? (
              // This should never come up
              <Placeholder />
            ) : activeBrowserRoot?.browserType === 'wandb' ? (
              <CenterEntityBrowser
                navigateToExpression={navigateToExpression}
                setPreviewNode={setPreviewNode}
                entityName={activeBrowserRoot?.rootId}
              />
            ) : activeBrowserRoot?.browserType === 'drafts' ? (
              activeBrowserRoot?.rootId === 'local' ? (
                <CenterLocalBrowser
                  navigateToExpression={navigateToExpression}
                  setPreviewNode={setPreviewNode}
                />
              ) : (
                // This should never come up
                <Placeholder />
              )
            ) : (
              // This should never come up
              <Placeholder />
            )}
          </CenterSpace>
        )}
        {/* Right Bar */}
        <LayoutElements.Block
          style={{
            width: previewNode != null ? '450px' : '0px',
          }}>
          {previewNode}
        </LayoutElements.Block>
      </LayoutElements.HSpace>
    </LayoutElements.VStack>
  );
};

const Placeholder: React.FC = props => {
  return (
    <LayoutElements.VStack
      style={{
        alignContent: 'center',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
      <IconWeaveLogo
        style={{
          width: '200px',
          height: '200px',
        }}
      />
    </LayoutElements.VStack>
  );
};

export const Home = memo(HomeComp);
