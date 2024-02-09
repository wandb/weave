import {LinearProgress} from '@material-ui/core';
import {Close, Fullscreen, Home} from '@mui/icons-material';
import {
  AppBar,
  Box,
  Breadcrumbs,
  Drawer,
  IconButton,
  Link as MaterialLink,
  Toolbar,
  Typography,
} from '@mui/material';
import {LicenseInfo} from '@mui/x-license-pro';
import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import _ from 'lodash';
import React, {
  ComponentProps,
  FC,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  Link as RouterLink,
  Route,
  Switch,
  useHistory,
  useParams,
} from 'react-router-dom';

import {MOON_200} from '../../../common/css/color.styles';
import {useWeaveContext} from '../../../context';
import {URL_BROWSE3} from '../../../urls';
import {ErrorBoundary} from '../../ErrorBoundary';
import {Browse2EntityPage} from './Browse2/Browse2EntityPage';
import {Browse2HomePage} from './Browse2/Browse2HomePage';
// import {RouteAwareBrowse3ProjectSideNav} from './Browse3/Browse3SideNav';
import {
  baseContext,
  browse2Context,
  Browse3WeaveflowRouteContextProvider,
  useClosePeek,
  usePeekLocation,
  useWeaveflowCurrentRouteContext,
  useWeaveflowRouteContext,
  WeaveflowPeekContext,
} from './Browse3/context';
import {BoardPage} from './Browse3/pages/BoardPage';
import {BoardsPage} from './Browse3/pages/BoardsPage';
import {CallPage} from './Browse3/pages/CallPage/CallPage';
import {CallsPage} from './Browse3/pages/CallsPage/CallsPage';
import {CenteredAnimatedLoader} from './Browse3/pages/common/Loader';
import {SimplePageLayoutContext} from './Browse3/pages/common/SimplePageLayout';
import {CompareCallsPage} from './Browse3/pages/CompareCallsPage';
import {ObjectPage} from './Browse3/pages/ObjectPage';
import {ObjectsPage} from './Browse3/pages/ObjectsPage';
import {ObjectVersionPage} from './Browse3/pages/ObjectVersionPage';
import {ObjectVersionsPage} from './Browse3/pages/ObjectVersionsPage';
import {OpPage} from './Browse3/pages/OpPage';
import {OpsPage} from './Browse3/pages/OpsPage';
import {OpVersionPage} from './Browse3/pages/OpVersionPage';
import {OpVersionsPage} from './Browse3/pages/OpVersionsPage';
import {TablePage} from './Browse3/pages/TablePage';
import {TablesPage} from './Browse3/pages/TablesPage';
import {TypePage} from './Browse3/pages/TypePage';
import {TypesPage} from './Browse3/pages/TypesPage';
import {TypeVersionPage} from './Browse3/pages/TypeVersionPage';
import {TypeVersionsPage} from './Browse3/pages/TypeVersionsPage';
import {useURLSearchParamsDict} from './Browse3/pages/util';
import {useCall} from './Browse3/pages/wfReactInterface/interface';
import {SideNav} from './Browse3/SideNav';
import {useDrawerResize} from './useDrawerResize';
import {useFlexDirection} from './useFlexDirection';

LicenseInfo.setLicenseKey(
  '7684ecd9a2d817a3af28ae2a8682895aTz03NjEwMSxFPTE3MjgxNjc2MzEwMDAsUz1wcm8sTE09c3Vic2NyaXB0aW9uLEtWPTI='
);

type Browse3Params = Partial<Browse3ProjectParams> &
  Partial<Browse3TabParams> &
  Partial<Browse3TabItemParams> &
  Partial<Browse3TabItemVersionParams>;

type Browse3ProjectMountedParams = Browse3ProjectParams &
  Partial<Browse3TabParams> &
  Partial<Browse3TabItemParams> &
  Partial<Browse3TabItemVersionParams>;

type Browse3ProjectParams = {
  entity: string;
  project: string;
};

type Browse3TabParams = {
  entity: string;
  project: string;
  tab: string;
};

type Browse3TabItemParams = {
  entity: string;
  project: string;
  tab: string;
  itemName: string;
};

type Browse3TabItemVersionParams = {
  entity: string;
  project: string;
  tab: string;
  itemName: string;
  version: string;
};

const tabOptions = [
  'types',
  'type-versions',
  'objects',
  'object-versions',
  'ops',
  'op-versions',
  'calls',
  'boards',
  'tables',
  'compare-calls',
];
const tabs = tabOptions.join('|');
const browse3Paths = (projectRoot: string) => [
  `${projectRoot}/:tab(${tabs})/:itemName/versions/:version/:refExtra*`,
  `${projectRoot}/:tab(${tabs})/:itemName`,
  `${projectRoot}/:tab(${tabs})`,
  `${projectRoot}`,
];

const SIDEBAR_WIDTH = 56;
const NAVBAR_HEIGHT = 60;

export const Browse3: FC<{
  hideHeader?: boolean;
  headerOffset?: number;
  navigateAwayFromProject?: () => void;
  projectRoot(entityName: string, projectName: string): string;
}> = props => {
  // const weaveContext = useWeaveContext();
  // useEffect(() => {
  //   const previousPolling = weaveContext.client.isPolling();
  //   weaveContext.client.setPolling(true);
  //   return () => {
  //     weaveContext.client.setPolling(previousPolling);
  //   };
  // }, [props.projectRoot, weaveContext]);
  return (
    <Browse3WeaveflowRouteContextProvider projectRoot={props.projectRoot}>
      <Switch>
        <Route
          path={[
            ...browse3Paths(props.projectRoot(':entity', ':project')),
            `/${URL_BROWSE3}/:entity`,
            `/${URL_BROWSE3}`,
          ]}>
          <Browse3Mounted
            hideHeader={props.hideHeader}
            headerOffset={props.headerOffset}
            navigateAwayFromProject={props.navigateAwayFromProject}
          />
        </Route>
      </Switch>
    </Browse3WeaveflowRouteContextProvider>
  );
};

const Browse3Mounted: FC<{
  hideHeader?: boolean;
  headerOffset?: number;
  navigateAwayFromProject?: () => void;
}> = props => {
  const {baseRouter} = useWeaveflowRouteContext();
  const weaveContext = useWeaveContext();
  const [weaveLoading, setWeaveLoading] = useState(false);
  useEffect(() => {
    const obs = weaveContext.client.loadingObservable();
    const sub = obs.subscribe(loading => {
      setWeaveLoading(loading);
    });
    return () => sub.unsubscribe();
  }, [weaveContext.client]);
  return (
    <Box
      sx={{
        display: 'flex',
        height: `calc(100vh - ${props.headerOffset ?? 0}px)`,
        overflow: 'auto',
        flexDirection: 'column',
      }}>
      {weaveLoading && (
        <Box
          sx={{
            width: '100%',
            position: 'absolute',
            zIndex: 2,
          }}>
          <LinearProgress />
        </Box>
      )}
      {!props.hideHeader && (
        <AppBar
          sx={{
            zIndex: theme => theme.zIndex.drawer + 1,
            height: '60px',
            flex: '0 0 auto',
            position: 'static',
          }}>
          <Toolbar
            sx={{
              backgroundColor: '#1976d2',
              minHeight: '30px',
            }}>
            <IconButton
              component={RouterLink}
              to={`/`}
              sx={{
                color: theme =>
                  theme.palette.getContrastText(theme.palette.primary.main),
                '&:hover': {
                  color: theme =>
                    theme.palette.getContrastText(theme.palette.primary.dark),
                },
                marginRight: theme => theme.spacing(2),
              }}>
              <Home />
            </IconButton>
            <Browse3Breadcrumbs />
          </Toolbar>
        </AppBar>
      )}
      <Switch>
        <Route path={baseRouter.projectUrl(':entity', ':project')} exact>
          <ProjectRedirect />
        </Route>
        <Route
          path={browse3Paths(baseRouter.projectUrl(':entity', ':project'))}>
          <Box
            component="main"
            sx={{
              flex: '1 1 auto',
              height: '100%',
              width: '100%',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'row',
            }}>
            <SideNav />
            {/* <RouteAwareBrowse3ProjectSideNav
              navigateAwayFromProject={props.navigateAwayFromProject}
            /> */}
            <Box
              component="main"
              sx={{
                flex: '1 1 auto',
                height: '100%',
                width: '100%',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
              }}>
              <ErrorBoundary>
                {/* <Browse3ProjectRootORMProvider> */}
                <MainPeekingLayout />
                {/* </Browse3ProjectRootORMProvider> */}
              </ErrorBoundary>
            </Box>
          </Box>
        </Route>

        <Route>
          <Box component="main" sx={{flexGrow: 1, p: 3}}>
            <Switch>
              <Route path={`/${URL_BROWSE3}/:entity`}>
                <Browse2EntityPage />
              </Route>
              <Route path={`/${URL_BROWSE3}`}>
                <Browse2HomePage />
              </Route>
            </Switch>
          </Box>
        </Route>
      </Switch>
    </Box>
  );
};

const MainPeekingLayout: FC = () => {
  const history = useHistory();
  const {baseRouter} = useWeaveflowRouteContext();
  const params = useParams<Browse3Params>();
  const baseRouterProjectRoot = baseRouter.projectUrl(':entity', ':project');
  const generalProjectRoot = browse2Context.projectUrl(':entity', ':project');
  const query = useURLSearchParamsDict();
  const peekLocation = usePeekLocation();
  const generalBase = browse2Context.projectUrl(
    params.entity!,
    params.project!
  );
  const targetBase = baseRouter.projectUrl(params.entity!, params.project!);
  const flexDirection = useFlexDirection();
  const isFlexRow = flexDirection === 'row';
  const isDrawerOpen = peekLocation != null;
  const windowSize = useWindowSize();

  const {handleMousedown, drawerWidthPct, drawerHeightPct} = useDrawerResize();
  const closePeek = useClosePeek();

  return (
    <Box
      sx={{
        flex: '1 1 auto',
        width: '100%',
        height: '100%',
        display: 'flex',
        overflow: 'hidden',
        flexDirection,
        alignContent: 'stretch',
      }}>
      <Box
        sx={{
          flex: '1 1 40%',
          overflow: 'hidden',
          display: 'flex',
          // This transition is from the mui drawer component, to keep the main content animation in similar
          transition: !isDrawerOpen
            ? 'margin 225ms cubic-bezier(0, 0, 0.2, 1) 0ms'
            : 'none',
          marginRight:
            !isDrawerOpen || !isFlexRow
              ? 0
              : `${(drawerWidthPct * windowSize.width) / 100}px`,
          // this is px hack to account for the navbar hiehgt
          marginBottom:
            !isDrawerOpen || isFlexRow
              ? 0
              : `${
                  (drawerHeightPct * (windowSize.height - NAVBAR_HEIGHT)) / 100
                }px`,
        }}>
        <Browse3ProjectRoot projectRoot={baseRouterProjectRoot} />
      </Box>

      <Drawer
        variant="persistent"
        anchor={isFlexRow ? 'right' : 'bottom'}
        open={isDrawerOpen}
        onClose={closePeek}
        PaperProps={{
          style: {
            overflow: 'hidden',
            display: 'flex',
            zIndex: 1,
            width: isFlexRow
              ? `${drawerWidthPct}%`
              : `calc(100% - ${SIDEBAR_WIDTH}px)`,
            height: !isFlexRow ? `${drawerHeightPct}%` : '100%',
            margin: isFlexRow ? 0 : `0 0 0 ${SIDEBAR_WIDTH + 1}px`,
            boxShadow: isFlexRow
              ? 'rgba(15, 15, 15, 0.04) 0px 0px 0px 1px, rgba(15, 15, 15, 0.03) 0px 3px 6px, rgba(15, 15, 15, 0.06) 0px 9px 24px'
              : 'rgba(15, 15, 15, 0.04) 0px 0px 0px 1px, rgba(15, 15, 15, 0.03) 3px 0px 6px, rgba(15, 15, 15, 0.06) 9px 0px 24px',
            borderLeft: isFlexRow ? `1px solid ${MOON_200}` : 'none',
            borderTop: !isFlexRow ? `1px solid ${MOON_200}` : 'none',
            position: 'absolute',
          },
        }}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile.
        }}>
        <div
          id="dragger"
          onMouseDown={handleMousedown}
          style={{
            borderTop: '1px solid #ddd',
            position: 'absolute',
            top: 0,
            left: 0,
            zIndex: 100,
            backgroundColor: '#f4f7f9',
            cursor: isFlexRow ? 'ew-resize' : 'ns-resize',
            padding: isFlexRow ? '4px 0 0' : '0 4px 0 0',
            bottom: isFlexRow ? 0 : 'auto',
            right: isFlexRow ? 'auto' : 0,
            width: isFlexRow ? '5px' : 'auto',
            height: isFlexRow ? 'auto' : '5px',
          }}
        />
        {peekLocation && (
          <WeaveflowPeekContext.Provider value={{isPeeking: true}}>
            <SimplePageLayoutContext.Provider
              value={{
                headerPrefix: (
                  <>
                    <Box
                      sx={{
                        flex: '0 0 auto',
                        height: '47px',
                      }}>
                      <IconButton
                        onClick={() => {
                          closePeek();
                        }}>
                        <Close />
                      </IconButton>
                    </Box>
                    <Box
                      sx={{
                        flex: '0 0 auto',
                        height: '47px',
                      }}>
                      <IconButton
                        onClick={() => {
                          const targetPath = query.peekPath!.replace(
                            generalBase,
                            targetBase
                          );
                          history.push(targetPath);
                        }}>
                        <Fullscreen />
                      </IconButton>
                    </Box>
                  </>
                ),
              }}>
              <Browse3ProjectRoot
                customLocation={peekLocation}
                projectRoot={generalProjectRoot}
              />
            </SimplePageLayoutContext.Provider>
          </WeaveflowPeekContext.Provider>
        )}
      </Drawer>
    </Box>
  );
};

const ProjectRedirect: FC = () => {
  const history = useHistory();
  const params = useParams<Browse3ProjectMountedParams>();
  const {baseRouter} = useWeaveflowRouteContext();

  useEffect(() => {
    if (params.tab == null) {
      history.replace(
        baseRouter.opVersionsUIUrl(params.entity, params.project, {})
        // baseRouter.callsUIUrl(params.entity ?? '', params.project ?? '', {
        //   traceRootsOnly: true,
        // })
      );
    }
  }, [baseRouter, history, params.entity, params.project, params.tab]);

  return <CenteredAnimatedLoader />;
};

const Browse3ProjectRoot: FC<{
  projectRoot: string;
  customLocation?: {
    key: string;
    pathname: string;
    search: string;
    hash: string;
    state: any;
  };
}> = ({projectRoot, customLocation}) => {
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        width: '100%',
        overflowY: 'auto',
        // Very odd, but this is needed to prevent the horizontal scrollbar for a single pixel
        overflowX: 'hidden',
      }}>
      <Switch location={customLocation}>
        {/* TYPES */}
        <Route path={`${projectRoot}/types/:itemName/versions/:version?`}>
          <TypeVersionRoutePageBinding />
        </Route>
        <Route path={`${projectRoot}/types/:itemName`}>
          <TypePageBinding />
        </Route>
        <Route path={`${projectRoot}/types`}>
          <TypesPageBinding />
        </Route>
        <Route path={`${projectRoot}/type-versions`}>
          <TypeVersionsPageBinding />
        </Route>
        {/* OBJECTS */}
        <Route
          path={`${projectRoot}/objects/:itemName/versions/:version?/:refExtra*`}>
          <ObjectVersionRoutePageBinding />
        </Route>
        <Route path={`${projectRoot}/objects/:itemName`}>
          <ObjectPageBinding />
        </Route>
        <Route path={`${projectRoot}/objects`}>
          <ObjectsPageBinding />
        </Route>
        <Route path={`${projectRoot}/object-versions`}>
          <ObjectVersionsPageBinding />
        </Route>
        {/* OPS */}
        <Route path={`${projectRoot}/ops/:itemName/versions/:version?`}>
          <OpVersionRoutePageBinding />
        </Route>
        <Route path={`${projectRoot}/ops/:itemName`}>
          <OpPageBinding />
        </Route>
        <Route path={`${projectRoot}/ops`}>
          <OpsPageBinding />
        </Route>
        <Route path={`${projectRoot}/op-versions`}>
          <OpVersionsPageBinding />
        </Route>
        {/* CALLS */}
        <Route path={`${projectRoot}/calls/:itemName`}>
          <CallPageBinding />
        </Route>
        <Route path={`${projectRoot}/calls`}>
          <CallsPageBinding />
        </Route>
        {/* BOARDS */}
        <Route
          path={[
            `${projectRoot}/boards/_new_board_`,
            `${projectRoot}/boards/:boardId`,
            `${projectRoot}/boards/:boardId/version/:versionId`,
          ]}>
          <BoardPageBinding />
        </Route>
        <Route path={`${projectRoot}/boards`}>
          <BoardsPageBinding />
        </Route>
        {/* TABLES */}
        <Route path={`${projectRoot}/tables/:tableId`}>
          <TablePage />
        </Route>
        <Route path={`${projectRoot}/tables`}>
          <TablesPageBinding />
        </Route>
        <Route path={`${projectRoot}/compare-calls`}>
          <CompareCallsBinding />
        </Route>
      </Switch>
    </Box>
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const ObjectVersionRoutePageBinding = () => {
  const params = useParams<Browse3TabItemVersionParams>();
  const query = useURLSearchParamsDict();

  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  useEffect(() => {
    if (!params.version) {
      history.replace(
        routerContext.objectUIUrl(
          params.entity,
          params.project,
          params.itemName
        )
      );
    }
  }, [
    history,
    params.version,
    params.entity,
    params.itemName,
    params.project,
    routerContext,
  ]);

  if (!params.version) {
    return <>Redirecting...</>;
  }
  return (
    <ObjectVersionPage
      entity={params.entity}
      project={params.project}
      objectName={params.itemName}
      version={params.version}
      filePath={query.path ?? 'obj'} // Default to obj
      refExtra={query.extra ?? ''}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const OpVersionRoutePageBinding = () => {
  const params = useParams<Browse3TabItemVersionParams>();
  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  useEffect(() => {
    if (!params.version) {
      history.replace(
        routerContext.opUIUrl(params.entity, params.project, params.itemName)
      );
    }
  }, [
    history,
    params.version,
    params.entity,
    params.itemName,
    params.project,
    routerContext,
  ]);

  if (!params.version) {
    return <>Redirecting...</>;
  }
  return (
    <OpVersionPage
      entity={params.entity}
      project={params.project}
      opName={params.itemName}
      version={params.version}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const TypeVersionRoutePageBinding = () => {
  const params = useParams<Browse3TabItemVersionParams>();

  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  useEffect(() => {
    if (!params.version) {
      history.replace(
        routerContext.typeUIUrl(params.entity, params.project, params.itemName)
      );
    }
  }, [
    history,
    params.version,
    params.entity,
    params.project,
    params.itemName,
    routerContext,
  ]);

  if (!params.version) {
    return <>Redirecting...</>;
  }
  return (
    <TypeVersionPage
      entity={params.entity}
      project={params.project}
      typeName={params.itemName}
      version={params.version}
    />
  );
};

const useCallPeekRedirect = () => {
  // This is a "hack" since the client doesn't have all the info
  // needed to make a correct peek URL. This allows the client to request
  // such a view and we can redirect to the correct URL.
  const params = useParams<Browse3TabItemParams>();
  const {baseRouter} = useWeaveflowRouteContext();
  const history = useHistory();
  const {result: call} = useCall({
    entity: params.entity,
    project: params.project,
    callId: params.itemName,
  });
  const query = useURLSearchParamsDict();
  useEffect(() => {
    if (call && query.convertToPeek) {
      const opVersionRef = call.opVersionRef;
      if (!opVersionRef) {
        return;
      }
      const path = baseRouter.callsUIUrl(params.entity, params.project, {
        opVersionRefs: [opVersionRef],
      });
      const searchParams = new URLSearchParams();
      searchParams.set(
        'peekPath',
        baseContext.callUIUrl(
          params.entity,
          params.project,
          call.traceId,
          params.itemName
        )
      );
      const newSearch = searchParams.toString();
      const newUrl = `${path}&${newSearch}`;
      history.replace(newUrl);
    }
  }, [
    baseRouter,
    call,
    history,
    params.entity,
    params.itemName,
    params.project,
    query.convertToPeek,
  ]);
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const CallPageBinding = () => {
  useCallPeekRedirect();
  const params = useParams<Browse3TabItemParams>();

  return (
    <CallPage
      entity={params.entity}
      project={params.project}
      callId={params.itemName}
    />
  );
};

const CompareCallsBinding = () => {
  const params = useParams<Browse3TabItemParams>();
  const query = useURLSearchParamsDict();
  const compareSpec = useMemo(() => {
    const callIds = JSON.parse(query.callIds);
    const primaryDim = query.primaryDim;
    const secondaryDim = query.secondaryDim;

    return {
      callIds,
      primaryDim,
      secondaryDim,
    };
  }, [query.callIds, query.primaryDim, query.secondaryDim]);

  return (
    <CompareCallsPage
      entity={params.entity}
      project={params.project}
      callIds={compareSpec.callIds}
      primaryDim={compareSpec.primaryDim}
      secondaryDim={compareSpec.secondaryDim}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const CallsPageBinding = () => {
  const params = useParams<Browse3TabParams>();
  const query = useURLSearchParamsDict();
  const filters = useMemo(() => {
    if (query.filter === undefined) {
      return {};
    }
    try {
      return JSON.parse(query.filter);
    } catch (e) {
      console.log(e);
      return {};
    }
  }, [query.filter]);
  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  const onFilterUpdate = useCallback(
    filter => {
      history.push(
        routerContext.callsUIUrl(params.entity, params.project, filter)
      );
    },
    [history, params.entity, params.project, routerContext]
  );
  return (
    <CallsPage
      entity={params.entity}
      project={params.project}
      initialFilter={filters}
      onFilterUpdate={onFilterUpdate}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const ObjectVersionsPageBinding = () => {
  const params = useParams<Browse3TabParams>();

  const query = useURLSearchParamsDict();
  const filters = useMemo(() => {
    if (query.filter === undefined) {
      return {};
    }
    try {
      return JSON.parse(query.filter);
    } catch (e) {
      console.log(e);
      return {};
    }
  }, [query.filter]);
  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  const onFilterUpdate = useCallback(
    filter => {
      history.push(
        routerContext.objectVersionsUIUrl(params.entity, params.project, filter)
      );
    },
    [history, params.entity, params.project, routerContext]
  );
  return (
    <ObjectVersionsPage
      entity={params.entity}
      project={params.project}
      initialFilter={filters}
      onFilterUpdate={onFilterUpdate}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const TypeVersionsPageBinding = () => {
  const params = useParams<Browse3TabParams>();

  const query = useURLSearchParamsDict();
  const filters = useMemo(() => {
    if (query.filter === undefined) {
      return {};
    }
    try {
      return JSON.parse(query.filter);
    } catch (e) {
      console.log(e);
      return {};
    }
  }, [query.filter]);
  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  const onFilterUpdate = useCallback(
    filter => {
      history.push(
        routerContext.typeVersionsUIUrl(params.entity, params.project, filter)
      );
    },
    [history, params.entity, params.project, routerContext]
  );
  return (
    <TypeVersionsPage
      entity={params.entity}
      project={params.project}
      initialFilter={filters}
      onFilterUpdate={onFilterUpdate}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const OpVersionsPageBinding = () => {
  const params = useParams<Browse3TabParams>();

  const query = useURLSearchParamsDict();
  const filters = useMemo(() => {
    if (query.filter === undefined) {
      return {};
    }
    try {
      return JSON.parse(query.filter);
    } catch (e) {
      console.log(e);
      return {};
    }
  }, [query.filter]);
  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  const onFilterUpdate = useCallback(
    filter => {
      history.push(
        routerContext.opVersionsUIUrl(params.entity, params.project, filter)
      );
    },
    [history, params.entity, params.project, routerContext]
  );
  return (
    <OpVersionsPage
      entity={params.entity}
      project={params.project}
      initialFilter={filters}
      onFilterUpdate={onFilterUpdate}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const BoardPageBinding = () => {
  const params = useParams<Browse3TabItemVersionParams>();

  return (
    <BoardPage
      entity={params.entity}
      project={params.project}
      boardId={params.itemName}
      versionId={params.version}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const ObjectPageBinding = () => {
  const params = useParams<Browse3TabItemVersionParams>();
  return (
    <ObjectPage
      entity={params.entity}
      project={params.project}
      objectName={params.itemName}
    />
  );
};

const OpPageBinding = () => {
  const params = useParams<Browse3TabItemVersionParams>();
  return (
    <OpPage
      entity={params.entity}
      project={params.project}
      opName={params.itemName}
    />
  );
};

const TypePageBinding = () => {
  const params = useParams<Browse3TabItemParams>();

  return (
    <TypePage
      entity={params.entity}
      project={params.project}
      typeName={params.itemName}
    />
  );
};

const TypesPageBinding = () => {
  const params = useParams<Browse3TabItemParams>();

  return <TypesPage entity={params.entity} project={params.project} />;
};

const OpsPageBinding = () => {
  const params = useParams<Browse3TabItemParams>();

  return <OpsPage entity={params.entity} project={params.project} />;
};

const ObjectsPageBinding = () => {
  const params = useParams<Browse3TabItemParams>();

  return <ObjectsPage entity={params.entity} project={params.project} />;
};

const BoardsPageBinding = () => {
  const params = useParams<Browse3TabItemParams>();

  return <BoardsPage entity={params.entity} project={params.project} />;
};

const TablesPageBinding = () => {
  const params = useParams<Browse3TabItemParams>();

  return <TablesPage entity={params.entity} project={params.project} />;
};

const AppBarLink = (props: ComponentProps<typeof RouterLink>) => (
  <MaterialLink
    sx={{
      color: theme => theme.palette.getContrastText(theme.palette.primary.main),
      '&:hover': {
        color: theme =>
          theme.palette.getContrastText(theme.palette.primary.dark),
      },
    }}
    {...props}
    component={RouterLink}
  />
);

const Browse3Breadcrumbs: FC = props => {
  const params = useParams<Browse3Params>();
  const query = useURLSearchParamsDict();
  const filePathParts = query.path?.split('/') ?? [];
  const refFields = query.extra?.split('/') ?? [];

  return (
    <Breadcrumbs>
      {params.entity && (
        <AppBarLink to={`/${URL_BROWSE3}/${params.entity}`}>
          {params.entity}
        </AppBarLink>
      )}
      {params.project && (
        <AppBarLink to={`/${URL_BROWSE3}/${params.entity}/${params.project}`}>
          {params.project}
        </AppBarLink>
      )}
      {params.tab && (
        <AppBarLink
          to={`/${URL_BROWSE3}/${params.entity}/${params.project}/${params.tab}`}>
          {params.tab}
        </AppBarLink>
      )}
      {params.itemName && (
        <AppBarLink
          to={`/${URL_BROWSE3}/${params.entity}/${params.project}/${params.tab}/${params.itemName}`}>
          {params.itemName}
        </AppBarLink>
      )}
      {params.version && (
        <AppBarLink
          to={`/${URL_BROWSE3}/${params.entity}/${params.project}/${params.tab}/${params.itemName}/versions/${params.version}`}>
          {params.version}
        </AppBarLink>
      )}
      {filePathParts.map((part, idx) => (
        <AppBarLink
          key={idx}
          to={`/${URL_BROWSE3}/${params.entity}/${params.project}/${
            params.tab
          }/${params.itemName}/versions/${
            params.version
          }?path=${encodeURIComponent(
            filePathParts.slice(0, idx + 1).join('/')
          )}`}>
          {part}
        </AppBarLink>
      ))}
      {_.range(0, refFields.length, 2).map(idx => (
        <React.Fragment key={idx}>
          <Typography
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
            }}>
            {refFields[idx]}
          </Typography>
          <AppBarLink
            to={`/${URL_BROWSE3}/${params.entity}/${params.project}/${
              params.tab
            }/${params.itemName}/versions/${
              params.version
            }?path=${encodeURIComponent(
              filePathParts.join('/')
            )}&extra=${encodeURIComponent(
              refFields.slice(0, idx + 2).join('/')
            )}`}>
            {refFields[idx + 1]}
          </AppBarLink>
        </React.Fragment>
      ))}
    </Breadcrumbs>
  );
};
