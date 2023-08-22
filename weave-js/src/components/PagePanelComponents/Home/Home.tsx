import React, {FC, memo, useCallback, useMemo, useState} from 'react';

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
import {Redirect, useHistory, useParams} from 'react-router-dom';
import {
  URL_BROWSE,
  URL_LOCAL,
  URL_RECENT,
  URL_WANDB,
  urlEntity,
  urlLocalBoards,
  urlRecentBoards,
  urlRecentTables,
} from '../../../urls';

const CenterSpace = styled(LayoutElements.VSpace)`
  border: 1px solid ${MOON_250};
  box-shadow: 0px 8px 16px 0px #0e10140a;
  border-top-right-radius: 12px;
  border-top-left-radius: 12px;
`;

type HomeProps = {
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  inJupyter: boolean;
  browserType: string | undefined;
};

// Home Page TODO: Enable browsing recent assets
const RECENTS_SUPPORTED = false;

export type HomeParams = {
  entity: string | undefined;
  project: string | undefined;
  assetType: string | undefined;
  preview: string | undefined;
};

const HomeComp: FC<HomeProps> = props => {
  const history = useHistory();
  const params = useParams<HomeParams>();
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
                props.browserType === 'recent' && params.assetType === 'board',
              to: urlRecentBoards(),
              onClick: () => {
                setPreviewNode(undefined);
                history.push(urlRecentBoards());
              },
            },
            {
              icon: IconTable,
              label: `Tables`,
              active:
                props.browserType === 'recent' && params.assetType === 'table',
              to: urlRecentTables(),
              onClick: () => {
                setPreviewNode(undefined);
                history.push(urlRecentTables());
              },
            },
          ],
        },
      ];
    } else {
      return [];
    }
  }, [history, props.browserType, params.assetType]);

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
                  props.browserType === 'wandb' && params.entity === entity,
                to: urlEntity(entity),
                onClick: () => {
                  console.log('setpreview node undefined');
                  setPreviewNode(undefined);
                  history.push(urlEntity(entity));
                },
              })),
          },
        ];
  }, [
    params,
    history,
    props.browserType,
    userEntities.result,
    userName.result,
  ]);

  const localSection = useMemo(() => {
    if (!isLocallyServed) {
      return [];
    }
    return [
      {
        title: `Local`,
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
            active: props.browserType === 'local',
            to: urlLocalBoards(),
            onClick: () => {
              setPreviewNode(undefined);
              history.push(urlLocalBoards());
            },
          },
        ],
      },
    ];
  }, [history, props.browserType, isLocallyServed]);

  const navSections = useMemo(() => {
    return [...recentSection, ...wandbSection, ...localSection];
  }, [localSection, recentSection, wandbSection]);

  const loading = userName.loading || isAuthenticated === undefined;
  const REDIRECT_RECENTS = [
    `/${URL_BROWSE}/${URL_RECENT}`,
    `/${URL_BROWSE}/${URL_RECENT}/`,
  ];
  const REDIRECT_WANDB = [
    `/${URL_BROWSE}/${URL_WANDB}`,
    `/${URL_BROWSE}/${URL_WANDB}/`,
  ];
  const REDIRECT_LOCAL = [
    `/${URL_BROWSE}/${URL_LOCAL}`,
    `/${URL_BROWSE}/${URL_LOCAL}/`,
  ];
  if (RECENTS_SUPPORTED) {
    REDIRECT_RECENTS.push('/', `/${URL_BROWSE}`, `/${URL_BROWSE}/`);
  } else {
    REDIRECT_WANDB.push('/', `/${URL_BROWSE}`, `/${URL_BROWSE}/`);
  }
  const REDIRECT_ANY = [
    ...REDIRECT_RECENTS,
    ...REDIRECT_WANDB,
    ...REDIRECT_LOCAL,
  ];
  const {pathname} = window.location;
  if (!loading && REDIRECT_ANY.includes(pathname)) {
    // If we have Recent enabled, go for that!
    if (REDIRECT_RECENTS.includes(pathname)) {
      return <Redirect to={urlRecentBoards()} />;
    }
    // Next, if we are authenticated (we are always authed in the cloud)
    if (
      isAuthenticated &&
      userName.result != null &&
      REDIRECT_WANDB.includes(pathname)
    ) {
      // It would be super cool to go straight to the first project that has weave objects
      return <Redirect to={urlEntity(userName.result)} />;
    }
    if (isLocallyServed && REDIRECT_LOCAL.includes(pathname)) {
      return <Redirect to={urlLocalBoards()} />;
    }
    // This should never happen
    console.warn('Unable to determine root');
  }

  return (
    <LayoutElements.VStack>
      <LayoutElements.Block>
        <HomeTopBar />
      </LayoutElements.Block>
      {/* Main Region */}
      <LayoutElements.HSpace
        style={{
          gap: '12px',
        }}>
        {/* Left Bar */}
        <LeftNav
          sections={navSections}
          inJupyter={props.inJupyter}
          navigateToExpression={navigateToExpression}
        />
        {/* Center Content */}
        {!loading && (
          <CenterSpace>
            {props.browserType === 'recent' ? (
              // This should never come up
              <Placeholder />
            ) : props.browserType === 'wandb' ? (
              <CenterEntityBrowser
                navigateToExpression={navigateToExpression}
                setPreviewNode={setPreviewNode}
                entityName={params.entity ?? ''}
              />
            ) : props.browserType === 'local' ? (
              <CenterLocalBrowser
                navigateToExpression={navigateToExpression}
                setPreviewNode={setPreviewNode}
              />
            ) : (
              // This should never come up
              <Placeholder />
            )}
          </CenterSpace>
        )}
        {/* Right Bar */}
        <LayoutElements.Block
          style={{
            width: previewNode != null ? '400px' : '0px',
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
