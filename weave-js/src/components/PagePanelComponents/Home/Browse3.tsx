import {ApolloProvider} from '@apollo/client';
import {Box, Drawer} from '@mui/material';
import {
  GridColumnVisibilityModel,
  GridFilterModel,
  GridPaginationModel,
  GridPinnedColumnFields,
  GridSortModel,
} from '@mui/x-data-grid-pro';
import {LicenseInfo} from '@mui/x-license';
import {makeGorillaApolloClient} from '@wandb/weave/apollo';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/common/heuristics';
import {opVersionKeyToRefUri} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/utilities';
import {debounce} from 'lodash';
import React, {
  FC,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import useMousetrap from 'react-hook-mousetrap';
import {
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
import {ComparePage} from './Browse3/compare/ComparePage';
import {
  baseContext,
  browse2Context,
  Browse3WeaveflowRouteContextProvider,
  DESCENDENT_CALL_ID_PARAM,
  HIDE_TRACETREE_PARAM,
  PEEK_PARAM,
  SHOW_FEEDBACK_PARAM,
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
import {CallPage} from './Browse3/pages/CallPage/CallPage';
import {CallsPage} from './Browse3/pages/CallsPage/CallsPage';
import {
  ALWAYS_PIN_LEFT_CALLS,
  DEFAULT_FILTER_CALLS,
  DEFAULT_PIN_CALLS,
  DEFAULT_SORT_CALLS,
} from './Browse3/pages/CallsPage/CallsTable';
import {Empty} from './Browse3/pages/common/Empty';
import {EMPTY_NO_TRACE_SERVER} from './Browse3/pages/common/EmptyContent';
import {SimplePageLayoutContext} from './Browse3/pages/common/SimplePageLayout';
import {CompareEvaluationsPage} from './Browse3/pages/CompareEvaluationsPage/CompareEvaluationsPage';
import {LeaderboardListingPage} from './Browse3/pages/LeaderboardPage/LeaderboardListingPage';
import {LeaderboardPage} from './Browse3/pages/LeaderboardPage/LeaderboardPage';
import {ModsPage} from './Browse3/pages/ModsPage';
import {ObjectPage} from './Browse3/pages/ObjectsPage/ObjectPage';
import {WFHighLevelObjectVersionFilter} from './Browse3/pages/ObjectsPage/objectsPageTypes';
import {ObjectVersionPage} from './Browse3/pages/ObjectsPage/ObjectVersionPage';
import {ObjectVersionsPage} from './Browse3/pages/ObjectsPage/ObjectVersionsPage';
import {OpPage} from './Browse3/pages/OpsPage/OpPage';
import {OpsPage} from './Browse3/pages/OpsPage/OpsPage';
import {OpVersionPage} from './Browse3/pages/OpsPage/OpVersionPage';
import {OpVersionsPage} from './Browse3/pages/OpsPage/OpVersionsPage';
import {PlaygroundPage} from './Browse3/pages/PlaygroundPage/PlaygroundPage';
import {ScorersPage} from './Browse3/pages/ScorersPage/ScorersPage';
import {TablePage} from './Browse3/pages/TablePage';
import {TablesPage} from './Browse3/pages/TablesPage';
import {useURLSearchParamsDict} from './Browse3/pages/util';
import {
  useWFHooks,
  WFDataModelAutoProvider,
} from './Browse3/pages/wfReactInterface/context';
import {useHasTraceServerClientContext} from './Browse3/pages/wfReactInterface/traceServerClientContext';
import {TableRowSelectionProvider} from './TableRowSelectionContext';
import {useDrawerResize} from './useDrawerResize';

LicenseInfo.setLicenseKey(
  'c3f549c76a1e054e5e314b2f1ecfca1cTz05OTY3MixFPTE3NjAxMTM3NDAwMDAsUz1wcm8sTE09c3Vic2NyaXB0aW9uLFBWPWluaXRpYWwsS1Y9Mg=='
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
  'leaderboards',
  'boards',
  'tables',
  'mods',
  'scorers',
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
  gorillaApolloEndpoint?: string;
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
  const apolloClient = useMemo(
    () => makeGorillaApolloClient(props.gorillaApolloEndpoint),
    [props.gorillaApolloEndpoint]
  );
  return (
    <ApolloProvider client={apolloClient}>
      <Browse3WeaveflowRouteContextProvider projectRoot={props.projectRoot}>
        <Switch>
          <Route
            path={[
              ...browse3Paths(props.projectRoot(':entity', ':project')),
              `/${URL_BROWSE3}/:entity`,
              `/${URL_BROWSE3}`,
            ]}>
            <Browse3Mounted
              headerOffset={props.headerOffset}
              navigateAwayFromProject={props.navigateAwayFromProject}
            />
          </Route>
        </Switch>
      </Browse3WeaveflowRouteContextProvider>
    </ApolloProvider>
  );
};

const Browse3Mounted: FC<{
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
      </Switch>
    </Box>
  );
};

const MainPeekingLayout: FC = () => {
  const {baseRouter} = useWeaveflowRouteContext();
  const params = useParamsDecoded<Browse3Params>();
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

  const drawerRef = useRef<HTMLDivElement | null>(null);
  const {handleMousedown, drawerWidthPx} = useDrawerResize(drawerRef);

  // State to track whether the user is currently dragging the drawer resize handle
  const [isDragging, setIsDragging] = useState(false);

  // Callback function to handle the end of dragging
  const handleDragEnd = useCallback(() => {
    setIsDragging(false);
    document.body.style.cursor = '';
    window.removeEventListener('mouseup', handleDragEnd);
  }, []);

  // Callback function to handle the start of dragging
  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      setIsDragging(true);
      handleMousedown(e);
      document.body.style.cursor = 'col-resize';
      window.addEventListener('mouseup', handleDragEnd);
    },
    [handleDragEnd, handleMousedown]
  );

  const closePeek = useClosePeek();

  useMousetrap('esc', closePeek);

  return (
    <WFDataModelAutoProvider
      entityName={params.entity!}
      projectName={params.project!}>
      <TableRowSelectionProvider>
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
              marginRight: !isDrawerOpen ? 0 : `${drawerWidthPx}px`,
            }}>
            <Browse3ProjectRoot projectRoot={baseRouterProjectRoot} />
          </Box>

          <Drawer
            variant="persistent"
            anchor="right"
            open={isDrawerOpen}
            onClose={closePeek}
            PaperProps={{
              ref: drawerRef,
              style: {
                overflow: 'hidden',
                display: isDrawerOpen ? 'flex' : 'none',
                zIndex: 1,
                width: isDrawerOpen ? `${drawerWidthPx}px` : 0,
                height: '100%',
                borderLeft: '1px solid #e0e0e0',
                position: 'absolute',
                pointerEvents: isDragging ? 'none' : 'auto',
              },
            }}
            ModalProps={{
              keepMounted: true,
            }}>
            <div
              id="dragger"
              onMouseDown={handleDragStart}
              style={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                left: 0,
                width: '5px',
                cursor: 'col-resize',
                zIndex: 2,
              }}
            />
            {peekLocation && (
              <WeaveflowPeekContext.Provider value={{isPeeking: true}}>
                <SimplePageLayoutContext.Provider
                  value={{
                    headerSuffix: (
                      <Box sx={{flex: '0 0 auto'}}>
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
      </TableRowSelectionProvider>
    </WFDataModelAutoProvider>
  );
};

const ProjectRedirect: FC = () => {
  const {entity, project} = useParamsDecoded<Browse3ProjectMountedParams>();
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
            `${projectRoot}/:tab(prompts|datasets|models|objects)`,
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
        <Route path={`${projectRoot}/:tab(scorers)`}>
          <ScorersPageBinding />
        </Route>
        <Route
          path={[
            `${projectRoot}/leaderboards/:itemName`,
            `${projectRoot}/leaderboards`,
          ]}>
          <LeaderboardPageBinding />
        </Route>
        {/* TABLES */}
        <Route path={`${projectRoot}/tables/:tableId`}>
          <TablePage />
        </Route>
        <Route path={`${projectRoot}/tables`}>
          <TablesPageBinding />
        </Route>
        {/* MODS */}
        <Route
          path={[`${projectRoot}/mods/:itemName`, `${projectRoot}/:tab(mods)`]}>
          <ModsPageBinding />
        </Route>
        {/* PLAYGROUND */}
        <Route
          path={[
            `${projectRoot}/playground/:itemName`,
            `${projectRoot}/playground`,
          ]}>
          <PlaygroundPageBinding />
        </Route>
        <Route path={`${projectRoot}/compare`}>
          <ComparePageBinding />
        </Route>
      </Switch>
    </Box>
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const ObjectVersionRoutePageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemVersionParams>();
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
  const params = useParamsDecoded<Browse3TabItemVersionParams>();
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
  const params = useParamsDecoded<Browse3TabItemParams>();
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

const useParamsDecoded = <T extends object>() => {
  // Handle the case where entity/project (old) have spaces
  const params = useParams<T>();
  return useMemo(() => {
    return Object.fromEntries(
      Object.entries(params).map(([key, value]) => [
        key,
        decodeURIComponent(value),
      ])
    );
  }, [params]);
};

const getOptionalBoolean = (
  dict: Record<string, string>,
  key: string
): boolean | undefined => {
  const value = dict[key];
  if (value == null) {
    return undefined;
  }
  return value === '1';
};

const getOptionalString = (
  dict: Record<string, string>,
  key: string
): string | undefined => {
  const value = dict[key];
  if (value == null) {
    return undefined;
  }
  return value;
};

const useURLBackedCallPageState = () => {
  const params = useParamsDecoded<Browse3TabItemParams>();
  const query = useURLSearchParamsDict();
  const history = useHistory();
  const currentRouter = useWeaveflowCurrentRouteContext();
  const [rootCallId, setRootCallId] = useState(params.itemName);
  useEffect(() => {
    setRootCallId(params.itemName);
  }, [params.itemName]);

  const [descendentCallId, setDescendentCallId] = useState<string | undefined>(
    getOptionalString(query, DESCENDENT_CALL_ID_PARAM)
  );
  useEffect(() => {
    setDescendentCallId(getOptionalString(query, DESCENDENT_CALL_ID_PARAM));
  }, [query]);

  const [showFeedback, setShowFeedback] = useState<boolean | undefined>(
    getOptionalBoolean(query, SHOW_FEEDBACK_PARAM)
  );
  useEffect(() => {
    setShowFeedback(getOptionalBoolean(query, SHOW_FEEDBACK_PARAM));
  }, [query]);

  const [hideTraceTree, setHideTraceTree] = useState<boolean | undefined>(
    getOptionalBoolean(query, HIDE_TRACETREE_PARAM)
  );
  useEffect(() => {
    setHideTraceTree(getOptionalBoolean(query, HIDE_TRACETREE_PARAM));
  }, [query]);

  const debouncedHistoryPush = useMemo(() => {
    return debounce((path: string) => {
      if (history.location.pathname + history.location.search !== path) {
        history.push(path);
      }
    }, 500);
  }, [history]);

  useEffect(() => {
    debouncedHistoryPush(
      currentRouter.callUIUrl(
        params.entity,
        params.project,
        '',
        rootCallId,
        descendentCallId,
        hideTraceTree,
        showFeedback
      )
    );
    return () => {
      debouncedHistoryPush.cancel();
    };
  }, [
    currentRouter,
    debouncedHistoryPush,
    params.entity,
    params.project,
    rootCallId,
    descendentCallId,
    showFeedback,
    hideTraceTree,
  ]);

  return {
    entity: params.entity,
    project: params.project,
    rootCallId,
    descendentCallId,
    showFeedback,
    hideTraceTree,
    setRootCallId,
    setDescendentCallId,
    setShowFeedback,
    setHideTraceTree,
  };
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const CallPageBinding = () => {
  useCallPeekRedirect();
  const {
    entity,
    project,
    rootCallId,
    descendentCallId,
    showFeedback,
    hideTraceTree,
    setRootCallId,
    setDescendentCallId,
    setShowFeedback,
    setHideTraceTree,
  } = useURLBackedCallPageState();

  return (
    <CallPage
      entity={entity}
      project={project}
      rootCallId={rootCallId}
      setRootCallId={setRootCallId}
      descendentCallId={descendentCallId}
      setDescendentCallId={setDescendentCallId}
      hideTraceTree={hideTraceTree}
      setHideTraceTree={setHideTraceTree}
      showFeedback={showFeedback}
      setShowFeedback={setShowFeedback}
    />
  );
};

// TODO(tim/weaveflow_improved_nav): Generalize this
const CallsPageBinding = () => {
  const {entity, project, tab} = useParamsDecoded<Browse3TabParams>();
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
      return {};
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
  const setPinModel = (newModel: GridPinnedColumnFields) => {
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
  const {entity, project, tab} = useParamsDecoded<Browse3TabParams>();
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

    // Set the baseObjectClass filter based on the tab
    if (tab === 'prompts') {
      queryFilter.baseObjectClass = 'Prompt';
    } else if (tab === 'models') {
      queryFilter.baseObjectClass = 'Model';
    } else if (tab === 'datasets') {
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
  const params = useParamsDecoded<Browse3TabParams>();

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
const ObjectPageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemVersionParams>();
  return (
    <ObjectPage
      entity={params.entity}
      project={params.project}
      objectName={params.itemName}
    />
  );
};

const OpPageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemVersionParams>();
  return (
    <OpPage
      entity={params.entity}
      project={params.project}
      opName={params.itemName}
    />
  );
};

const CompareEvaluationsBinding = () => {
  const history = useHistory();
  const routerContext = useWeaveflowCurrentRouteContext();
  const {entity, project} = useParamsDecoded<Browse3TabParams>();
  const query = useURLSearchParamsDict();
  const evaluationCallIds = useMemo(() => {
    return JSON.parse(query.evaluationCallIds);
  }, [query.evaluationCallIds]);
  const selectedMetrics: Record<string, boolean> | null = useMemo(() => {
    try {
      return JSON.parse(query.metrics);
    } catch (e) {
      return null;
    }
  }, [query.metrics]);
  const onEvaluationCallIdsUpdate = useCallback(
    (newEvaluationCallIds: string[]) => {
      history.push(
        routerContext.compareEvaluationsUri(
          entity,
          project,
          newEvaluationCallIds,
          selectedMetrics
        )
      );
    },
    [history, entity, project, routerContext, selectedMetrics]
  );
  const setSelectedMetrics = useCallback(
    (newModel: Record<string, boolean>) => {
      history.push(
        routerContext.compareEvaluationsUri(
          entity,
          project,
          evaluationCallIds,
          newModel
        )
      );
    },
    [history, entity, project, routerContext, evaluationCallIds]
  );
  return (
    <CompareEvaluationsPage
      entity={entity}
      project={project}
      evaluationCallIds={evaluationCallIds}
      onEvaluationCallIdsUpdate={onEvaluationCallIdsUpdate}
      selectedMetrics={selectedMetrics}
      setSelectedMetrics={setSelectedMetrics}
    />
  );
};

const ScorersPageBinding = () => {
  const {entity, project} = useParamsDecoded<Browse3TabParams>();
  return <ScorersPage entity={entity} project={project} />;
};

const LeaderboardPageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemParams>();
  const {entity, project, itemName: leaderboardName} = params;
  const query = useURLSearchParamsDict();
  const edit = query.edit === 'true';
  if (!leaderboardName) {
    return <LeaderboardListingPage entity={entity} project={project} />;
  }
  return (
    <LeaderboardPage
      entity={entity}
      project={project}
      leaderboardName={leaderboardName}
      openEditorOnMount={edit}
    />
  );
};

const OpsPageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemParams>();

  return <OpsPage entity={params.entity} project={params.project} />;
};

const ModsPageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemVersionParams>();
  return (
    <ModsPage
      entity={params.entity}
      project={params.project}
      itemName={params.itemName}
    />
  );
};

const TablesPageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemParams>();

  return <TablesPage entity={params.entity} project={params.project} />;
};

const ComparePageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemParams>();

  return <ComparePage entity={params.entity} project={params.project} />;
};

const PlaygroundPageBinding = () => {
  const params = useParamsDecoded<Browse3TabItemParams>();
  return (
    <PlaygroundPage
      entity={params.entity}
      project={params.project}
      callId={params.itemName}
    />
  );
};
