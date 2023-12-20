import {Close, Fullscreen, Home} from '@mui/icons-material';
import {
  AppBar,
  Box,
  Breadcrumbs,
  IconButton,
  Link as MaterialLink,
  Toolbar,
  Typography,
} from '@mui/material';
import {LicenseInfo} from '@mui/x-license-pro';
import React, {FC, useCallback, useEffect, useMemo} from 'react';
import {
  Link as RouterLink,
  Route,
  Switch,
  useHistory,
  useParams,
} from 'react-router-dom';

import {useWeaveContext} from '../../../context';
import {useNodeValue} from '../../../react';
import {URL_BROWSE3} from '../../../urls';
import {ErrorBoundary} from '../../ErrorBoundary';
import {Browse2EntityPage} from './Browse2/Browse2EntityPage';
import {Browse2HomePage} from './Browse2/Browse2HomePage';
import {RouteAwareBrowse3ProjectSideNav} from './Browse3/Browse3SideNav';
import {
  Browse3WeaveflowRouteContextProvider,
  useWeaveflowPeekAwareRouteContext,
  useWeaveflowRouteContext,
} from './Browse3/context';
import {BoardPage} from './Browse3/pages/BoardPage';
import {BoardsPage} from './Browse3/pages/BoardsPage';
import {CallPage} from './Browse3/pages/CallPage';
import {CallsPage} from './Browse3/pages/CallsPage';
import {CenteredAnimatedLoader} from './Browse3/pages/common/Loader';
import {SimplePageLayoutContext} from './Browse3/pages/common/SimplePageLayout';
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
import {WeaveflowORMContextProvider} from './Browse3/pages/wfInterface/context';
import {
  fnNaiveBootstrapFeedback,
  fnNaiveBootstrapObjects,
  fnNaiveBootstrapRuns,
  WFNaiveProject,
} from './Browse3/pages/wfInterface/naive';

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
  refExtra?: string;
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
];
const tabs = tabOptions.join('|');
const browse3Paths = (projectRoot: string) => [
  `${projectRoot}/:tab(${tabs})/:itemName/versions/:version/:refExtra*`,
  `${projectRoot}/:tab(${tabs})/:itemName`,
  `${projectRoot}/:tab(${tabs})`,
  `${projectRoot}`,
];

export const Browse3: FC<{
  hideHeader?: boolean;
  headerOffset?: number;
  navigateAwayFromProject?: () => void;
  projectRoot(entityName: string, projectName: string): string;
}> = props => {
  const weaveContext = useWeaveContext();
  useEffect(() => {
    const previousPolling = weaveContext.client.isPolling();
    weaveContext.client.setPolling(true);
    return () => {
      weaveContext.client.setPolling(previousPolling);
    };
  }, [props.projectRoot, weaveContext]);
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

const usePeekLocation = (peekPath?: string) => {
  return useMemo(() => {
    if (peekPath == null) {
      return undefined;
    }
    const peekPathParts = peekPath.split('?');
    const peekPathname = peekPathParts[0];
    const peekSearch = peekPathParts[1] ?? '';
    const peekSearchParts = peekSearch.split('#');
    const peekSearchString = peekSearchParts[0];
    const peekHash = peekSearchParts[1] ?? '';

    return {
      key: 'peekLoc',
      pathname: peekPathname,
      search: peekSearchString,
      hash: peekHash,
      state: {
        '[userDefined]': true,
      },
    };
  }, [peekPath]);
};

const Browse3Mounted: FC<{
  hideHeader?: boolean;
  headerOffset?: number;
  navigateAwayFromProject?: () => void;
}> = props => {
  const history = useHistory();
  const {baseRouter, peekingRouter} = useWeaveflowRouteContext();
  const params = useParams<Browse3Params>();
  const baseRouterProjectRoot = baseRouter.projectUrl(':entity', ':project');
  const peekRouterProjectRoot = peekingRouter.projectUrl(':entity', ':project');
  const query = useURLSearchParamsDict();
  const peekLocation = usePeekLocation(query.peekPath ?? undefined);
  return (
    <Box
      sx={{
        display: 'flex',
        height: `calc(100vh - ${props.headerOffset ?? 0}px)`,
        overflow: 'auto',
        flexDirection: 'column',
      }}>
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
            <RouteAwareBrowse3ProjectSideNav
              navigateAwayFromProject={props.navigateAwayFromProject}
            />
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
                <Browse3ProjectRootORMProvider>
                  <Box
                    sx={{
                      flex: '1 1 auto',
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      overflow: 'hidden',
                      flexDirection: 'row',
                      alignContent: 'stretch',
                    }}>
                    <Box
                      sx={{
                        flex: '1 1 40%',
                        overflow: 'hidden',
                        display: 'flex',
                      }}>
                      <Browse3ProjectRoot projectRoot={baseRouterProjectRoot} />
                    </Box>

                    <Box
                      sx={{
                        borderLeft: '1px solid rgba(0, 0, 0, 0.12)',
                        flex: peekLocation ? '1 1 60%' : '0 0 0px',
                        transition: peekLocation ? 'all 0.2s ease-in-out' : '',
                        boxShadow:
                          'rgba(15, 15, 15, 0.04) 0px 0px 0px 1px, rgba(15, 15, 15, 0.03) 0px 3px 6px, rgba(15, 15, 15, 0.06) 0px 9px 24px',
                        overflow: 'hidden',
                        display: 'flex',
                        zIndex: 1,
                      }}>
                      {peekLocation && (
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
                                      history.push(history.location.pathname);
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
                                      const generalBase =
                                        peekingRouter.projectUrl(
                                          params.entity!,
                                          params.project!
                                        );
                                      const targetBase = baseRouter.projectUrl(
                                        params.entity!,
                                        params.project!
                                      );
                                      const targetPath =
                                        query.peekPath!.replace(
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
                            projectRoot={peekRouterProjectRoot}
                          />
                        </SimplePageLayoutContext.Provider>
                      )}
                    </Box>
                  </Box>
                </Browse3ProjectRootORMProvider>
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

const useNaiveProjectDataConnection = (entity: string, project: string) => {
  const objectsNode = useMemo(() => {
    return fnNaiveBootstrapObjects(entity, project);
  }, [entity, project]);
  const runsNode = useMemo(() => {
    return fnNaiveBootstrapRuns(entity, project);
  }, [entity, project]);
  const feedbackNode = useMemo(() => {
    return fnNaiveBootstrapFeedback(entity, project);
  }, [entity, project]);
  const objectsValue = useNodeValue(objectsNode);
  const runsValue = useNodeValue(runsNode);
  const feedbackValue = useNodeValue(feedbackNode);
  return useMemo(() => {
    if (
      objectsValue.result == null &&
      runsValue.result == null &&
      feedbackValue.result == null
    ) {
      return null;
    }
    const connection = new WFNaiveProject(entity, project, {
      objects: objectsValue.result,
      runs: runsValue.result,
      feedback: feedbackValue.result,
    });
    return connection;
  }, [
    entity,
    feedbackValue.result,
    objectsValue.result,
    project,
    runsValue.result,
  ]);
};

const Browse3ProjectRootORMProvider: FC = props => {
  const params = useParams<Browse3ProjectMountedParams>();
  const projectData = useNaiveProjectDataConnection(
    params.entity,
    params.project
  );
  if (!projectData) {
    return <CenteredAnimatedLoader />;
  }
  return (
    <WeaveflowORMContextProvider projectConnection={projectData}>
      {props.children}
    </WeaveflowORMContextProvider>
  );
};

const ProjectRedirect: FC = () => {
  const history = useHistory();
  const params = useParams<Browse3ProjectMountedParams>();
  const {baseRouter} = useWeaveflowRouteContext();

  useEffect(() => {
    if (params.tab == null) {
      history.replace(
        baseRouter.callsUIUrl(params.entity ?? '', params.project ?? '', {
          traceRootsOnly: true,
        })
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
        overflow: 'auto',
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
      </Switch>
    </Box>
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const ObjectVersionRoutePageBinding = () => {
  const params = useParams<Browse3TabItemVersionParams>();

  const history = useHistory();
  const routerContext = useWeaveflowPeekAwareRouteContext();
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
      refExtra={params.refExtra}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const OpVersionRoutePageBinding = () => {
  const params = useParams<Browse3TabItemVersionParams>();
  const history = useHistory();
  const routerContext = useWeaveflowPeekAwareRouteContext();
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
  const routerContext = useWeaveflowPeekAwareRouteContext();
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

// TODO(tim/weaveflow_improved_nav): Generalize this
const CallPageBinding = () => {
  const params = useParams<Browse3TabItemParams>();

  return (
    <CallPage
      entity={params.entity}
      project={params.project}
      callId={params.itemName}
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
  const routerContext = useWeaveflowPeekAwareRouteContext();
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
  const routerContext = useWeaveflowPeekAwareRouteContext();
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
  const routerContext = useWeaveflowPeekAwareRouteContext();
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
  const routerContext = useWeaveflowPeekAwareRouteContext();
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

const AppBarLink = (props: React.ComponentProps<typeof RouterLink>) => (
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
  const refFields = params.refExtra?.split('/') ?? [];

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
      {refFields.map((field, idx) =>
        field === 'index' ? (
          <Typography
            key={idx}
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
            }}>
            row
          </Typography>
        ) : field === 'pick' ? (
          <Typography
            key={idx}
            sx={{
              color: theme =>
                theme.palette.getContrastText(theme.palette.primary.main),
            }}>
            col
          </Typography>
        ) : (
          <AppBarLink
            key={idx}
            to={`/${URL_BROWSE3}/${params.entity}/${params.project}/${
              params.tab
            }/${params.itemName}/versions/${params.version}/${refFields
              .slice(0, idx + 1)
              .join('/')}`}>
            {field}
          </AppBarLink>
        )
      )}
    </Breadcrumbs>
  );
};
