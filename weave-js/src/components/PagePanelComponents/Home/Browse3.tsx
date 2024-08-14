import {Home} from '@mui/icons-material';
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
import {
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumns,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {LicenseInfo} from '@mui/x-license-pro';
import {useWindowSize} from '@wandb/weave/common/hooks/useWindowSize';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/heuristics';
import {opVersionKeyToRefUri} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/utilities';
import _ from 'lodash';
import React, {
  ComponentProps,
  FC,
  useCallback,
  useEffect,
  useMemo,
} from 'react';
import useMousetrap from 'react-hook-mousetrap';
import {
  Link as RouterLink,
  Redirect,
  Route,
  Switch,
  useHistory,
  useLocation,
  useParams,
} from 'react-router-dom';

import {URL_BROWSE3} from '../../../urls';
import {Button} from '../../Button';
import {ErrorBoundary} from '../../ErrorBoundary';
import {Browse2EntityPage} from './Browse2/Browse2EntityPage';
import {Browse2HomePage} from './Browse2/Browse2HomePage';
import {
  baseContext,
  browse2Context,
  Browse3WeaveflowRouteContextProvider,
  PATH_PARAM,
  PEEK_PARAM,
  useClosePeek,
  usePeekLocation,
  useWeaveflowCurrentRouteContext,
  useWeaveflowRouteContext,
  WeaveflowPeekContext,
} from './Browse3/context';
import {FullPageButton} from './Browse3/FullPageButton';
import {getValidFilterModel} from './Browse3/grid/filters';
import {
  DEFAULT_PAGE_SIZE,
  getValidPaginationModel,
} from './Browse3/grid/pagination';
import {getValidPinModel, removeAlwaysLeft} from './Browse3/grid/pin';
import {getValidSortModel} from './Browse3/grid/sort';
import {BoardPage} from './Browse3/pages/BoardPage';
import {BoardsPage} from './Browse3/pages/BoardsPage';
import {CallPage} from './Browse3/pages/CallPage/CallPage';
import {CallsPage} from './Browse3/pages/CallsPage/CallsPage';
import {
  ALWAYS_PIN_LEFT_CALLS,
  DEFAULT_COLUMN_VISIBILITY_CALLS,
  DEFAULT_FILTER_CALLS,
  DEFAULT_PIN_CALLS,
  DEFAULT_SORT_CALLS,
} from './Browse3/pages/CallsPage/CallsTable';
import {Empty} from './Browse3/pages/common/Empty';
import {EMPTY_NO_TRACE_SERVER} from './Browse3/pages/common/EmptyContent';
import {SimplePageLayoutContext} from './Browse3/pages/common/SimplePageLayout';
import {CompareEvaluationsPage} from './Browse3/pages/CompareEvaluationsPage/CompareEvaluationsPage';
import {ObjectPage} from './Browse3/pages/ObjectPage';
import {ObjectVersionPage} from './Browse3/pages/ObjectVersionPage';
import {
  ObjectVersionsPage,
  WFHighLevelObjectVersionFilter,
} from './Browse3/pages/ObjectVersionsPage';
import {OpPage} from './Browse3/pages/OpPage';
import {OpsPage} from './Browse3/pages/OpsPage';
import {OpVersionPage} from './Browse3/pages/OpVersionPage';
import {OpVersionsPage} from './Browse3/pages/OpVersionsPage';
import {TablePage} from './Browse3/pages/TablePage';
import {TablesPage} from './Browse3/pages/TablesPage';
import {useURLSearchParamsDict} from './Browse3/pages/util';
import {
  useWFHooks,
  WFDataModelAutoProvider,
} from './Browse3/pages/wfReactInterface/context';
import {useHasTraceServerClientContext} from './Browse3/pages/wfReactInterface/traceServerClientContext';
import {SIDEBAR_WIDTH, useDrawerResize} from './useDrawerResize';

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
  'evaluations',
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
  const hasTSContext = useHasTraceServerClientContext();
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
        {hasTSContext ? (
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
                flexDirection: 'column',
              }}>
              <ErrorBoundary>
                <MainPeekingLayout />
              </ErrorBoundary>
            </Box>
          </Route>
        ) : (
          <Empty {...EMPTY_NO_TRACE_SERVER} />
        )}

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
  const isDrawerOpen = peekLocation != null;
  const windowSize = useWindowSize();

  const {handleMousedown, drawerWidthPct} = useDrawerResize();
  const closePeek = useClosePeek();

  useMousetrap('esc', closePeek);

  return (
    <WFDataModelAutoProvider
      entityName={params.entity!}
      projectName={params.project!}>
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
            // This transition is from the mui drawer component, to keep the main content animation in similar
            transition: !isDrawerOpen
              ? 'margin 225ms cubic-bezier(0, 0, 0.2, 1) 0ms'
              : 'none',
            marginRight: !isDrawerOpen
              ? 0
              : // subtract the sidebar width
                `${
                  (drawerWidthPct * (windowSize.width - SIDEBAR_WIDTH)) / 100
                }px`,
          }}>
          <Browse3ProjectRoot projectRoot={baseRouterProjectRoot} />
        </Box>

        <Drawer
          variant="persistent"
          anchor="right"
          open={isDrawerOpen}
          onClose={closePeek}
          PaperProps={{
            style: {
              overflow: 'hidden',
              display: isDrawerOpen ? 'flex' : 'none',
              zIndex: 1,
              width: `${drawerWidthPct}%`,
              height: '100%',
              boxShadow: '0px 0px 40px 0px rgba(0, 0, 0, 0.16)',
              borderLeft: 0,
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
              position: 'absolute',
              inset: '0 auto 0 0',
              zIndex: 2,
              backgroundColor: 'transparent',
              cursor: 'col-resize',
              width: '5px',
            }}
          />
          {peekLocation && (
            <WeaveflowPeekContext.Provider value={{isPeeking: true}}>
              <SimplePageLayoutContext.Provider
                value={{
                  headerSuffix: (
                    <Box
                      sx={{
                        height: '41px',
                        flex: '0 0 auto',
                      }}>
                      <FullPageButton
                        query={query}
                        generalBase={generalBase}
                        targetBase={targetBase}
                      />
                      <Button
                        tooltip="Close drawer"
                        icon="close"
                        variant="ghost"
                        className="ml-4"
                        onClick={closePeek}
                      />
                    </Box>
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
    </WFDataModelAutoProvider>
  );
};

const ProjectRedirect: FC = () => {
  const {entity, project} = useParams<Browse3ProjectMountedParams>();
  const {baseRouter} = useWeaveflowRouteContext();
  const url = baseRouter.tracesUIUrl(entity, project);
  return <Redirect to={url} />;
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
        {/* OBJECTS */}
        <Route
          path={`${projectRoot}/objects/:itemName/versions/:version?/:refExtra*`}>
          <ObjectVersionRoutePageBinding />
        </Route>
        <Route path={`${projectRoot}/objects/:itemName`}>
          <ObjectPageBinding />
        </Route>
        <Route
          path={[
            `${projectRoot}/:tab(datasets|models|objects)`,
            `${projectRoot}/object-versions`,
          ]}>
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
        <Route
          path={[`${projectRoot}/operations`, `${projectRoot}/op-versions`]}>
          <OpVersionsPageBinding />
        </Route>
        {/* CALLS */}
        <Route path={`${projectRoot}/calls/:itemName`}>
          <CallPageBinding />
        </Route>
        <Route path={`${projectRoot}/:tab(evaluations|traces|calls)`}>
          <CallsPageBinding />
        </Route>
        <Route path={`${projectRoot}/:tab(compare-evaluations)`}>
          <CompareEvaluationsBinding />
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
      refExtra={query.extra}
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

const useCallPeekRedirect = () => {
  // This is a "hack" since the client doesn't have all the info
  // needed to make a correct peek URL. This allows the client to request
  // such a view and we can redirect to the correct URL.
  const params = useParams<Browse3TabItemParams>();
  const {baseRouter} = useWeaveflowRouteContext();
  const history = useHistory();
  const {useCall} = useWFHooks();
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
        PEEK_PARAM,
        baseContext.callUIUrl(
          params.entity,
          params.project,
          call.traceId,
          params.itemName,
          undefined
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
  const query = useURLSearchParamsDict();

  return (
    <CallPage
      entity={params.entity}
      project={params.project}
      callId={params.itemName}
      path={query[PATH_PARAM]}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const CallsPageBinding = () => {
  const {entity, project, tab} = useParams<Browse3TabParams>();
  const query = useURLSearchParamsDict();
  const initialFilter = useMemo(() => {
    if (tab === 'evaluations') {
      return {
        frozen: true,
        opVersionRefs: [
          opVersionKeyToRefUri({
            entity,
            project,
            opId: EVALUATE_OP_NAME_POST_PYDANTIC,
            versionHash: '*',
          }),
        ],
      };
    }
    if (query.filter === undefined) {
      return {};
    }
    try {
      return JSON.parse(query.filter);
    } catch (e) {
      console.log(e);
      return {};
    }
  }, [query.filter, entity, project, tab]);
  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  const onFilterUpdate = useCallback(
    filter => {
      history.push(routerContext.callsUIUrl(entity, project, filter));
    },
    [history, entity, project, routerContext]
  );

  const location = useLocation();
  const columnVisibilityModel = useMemo(() => {
    try {
      return JSON.parse(query.cols);
    } catch (e) {
      return DEFAULT_COLUMN_VISIBILITY_CALLS;
    }
  }, [query.cols]);
  const setColumnVisibilityModel = (newModel: GridColumnVisibilityModel) => {
    const newQuery = new URLSearchParams(location.search);
    newQuery.set('cols', JSON.stringify(newModel));
    history.push({search: newQuery.toString()});
  };

  const pinModel = useMemo(
    () => getValidPinModel(query.pin, DEFAULT_PIN_CALLS, ALWAYS_PIN_LEFT_CALLS),
    [query.pin]
  );
  const setPinModel = (newModel: GridPinnedColumns) => {
    const newQuery = new URLSearchParams(location.search);
    newQuery.set(
      'pin',
      JSON.stringify(removeAlwaysLeft(newModel, ALWAYS_PIN_LEFT_CALLS))
    );
    history.push({search: newQuery.toString()});
  };

  const filterModel = useMemo(
    () => getValidFilterModel(query.filters, DEFAULT_FILTER_CALLS),
    [query.filters]
  );
  const setFilterModel = (newModel: GridFilterModel) => {
    const newQuery = new URLSearchParams(location.search);
    if (newModel.items.length === 0) {
      newQuery.delete('filters');
    } else {
      newQuery.set('filters', JSON.stringify(newModel));
    }
    history.push({search: newQuery.toString()});
  };

  const sortModel = useMemo(
    () => getValidSortModel(query.sort, DEFAULT_SORT_CALLS),
    [query.sort]
  );
  const setSortModel = (newModel: GridSortModel) => {
    const newQuery = new URLSearchParams(location.search);
    if (newModel.length === 0) {
      newQuery.delete('sort');
    } else {
      newQuery.set('sort', JSON.stringify(newModel));
    }
    history.push({search: newQuery.toString()});
  };

  const paginationModel = useMemo(
    () => getValidPaginationModel(query.page, query.pageSize),
    [query.page, query.pageSize]
  );
  const setPaginationModel = (newModel: GridPaginationModel) => {
    const newQuery = new URLSearchParams(location.search);
    const {page, pageSize} = newModel;
    // TODO: If we change page size, should we reset page to 0?
    if (page === 0) {
      newQuery.delete('page');
    } else {
      newQuery.set('page', page.toString());
    }
    if (pageSize === DEFAULT_PAGE_SIZE) {
      newQuery.delete('pageSize');
    } else {
      newQuery.set('pageSize', pageSize.toString());
    }
    history.push({search: newQuery.toString()});
  };

  return (
    <CallsPage
      entity={entity}
      project={project}
      initialFilter={initialFilter}
      onFilterUpdate={onFilterUpdate}
      columnVisibilityModel={columnVisibilityModel}
      setColumnVisibilityModel={setColumnVisibilityModel}
      pinModel={pinModel}
      setPinModel={setPinModel}
      filterModel={filterModel}
      setFilterModel={setFilterModel}
      sortModel={sortModel}
      setSortModel={setSortModel}
      paginationModel={paginationModel}
      setPaginationModel={setPaginationModel}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const ObjectVersionsPageBinding = () => {
  const {entity, project, tab} = useParams<Browse3TabParams>();
  const query = useURLSearchParamsDict();
  const filters: WFHighLevelObjectVersionFilter = useMemo(() => {
    let queryFilter: WFHighLevelObjectVersionFilter = {};
    // Parse the filter from the query string
    if (query.filter) {
      try {
        queryFilter = JSON.parse(
          query.filter
        ) as WFHighLevelObjectVersionFilter;
      } catch (e) {
        console.log(e);
      }
    }

    // If the tab is models or datasets, set the baseObjectClass filter
    // directly from the tab
    if (tab === 'models') {
      queryFilter.baseObjectClass = 'Model';
    }
    if (tab === 'datasets') {
      queryFilter.baseObjectClass = 'Dataset';
    }
    return queryFilter;
  }, [query.filter, tab]);

  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  const onFilterUpdate = useCallback(
    filter => {
      history.push(routerContext.objectVersionsUIUrl(entity, project, filter));
    },
    [history, entity, project, routerContext]
  );
  return (
    <ObjectVersionsPage
      entity={entity}
      project={project}
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

const CompareEvaluationsBinding = () => {
  const {entity, project} = useParams<Browse3TabParams>();
  const query = useURLSearchParamsDict();
  const evaluationCallIds = useMemo(() => {
    return JSON.parse(query.evaluationCallIds);
  }, [query.evaluationCallIds]);
  return (
    <CompareEvaluationsPage
      entity={entity}
      project={project}
      evaluationCallIds={evaluationCallIds}
    />
  );
};

const OpsPageBinding = () => {
  const params = useParams<Browse3TabItemParams>();

  return <OpsPage entity={params.entity} project={params.project} />;
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
