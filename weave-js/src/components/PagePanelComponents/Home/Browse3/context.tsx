import {GridFilterModel} from '@mui/x-data-grid-pro';
import {
  isWandbArtifactRef,
  isWeaveObjectRef,
  ObjectRef,
  parseRef,
} from '@wandb/weave/react';
import _ from 'lodash';
import React, {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';
import {useHistory, useLocation} from 'react-router-dom';

import {WFHighLevelCallFilter} from './pages/CallsPage/callsTableFilter';
import {WFHighLevelObjectVersionFilter} from './pages/ObjectsPage/objectsPageTypes';
import {WFHighLevelOpVersionFilter} from './pages/OpsPage/opsPageTypes';
import {useURLSearchParamsDict} from './pages/util';
import {
  AWL_ROW_EDGE_NAME,
  DICT_KEY_EDGE_NAME,
  OBJECT_ATTR_EDGE_NAME,
} from './pages/wfReactInterface/constants';

const pruneEmptyFields = (filter: {[key: string]: any} | null | undefined) => {
  if (!filter) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(filter).filter(
      ([k, v]) =>
        v != null &&
        v !== undefined &&
        (_.isArray(v) ? v.length > 0 : true) &&
        (typeof v === 'string' ? v.length > 0 : true)
    )
  );
};

export const useWeaveflowRouteContext = () => {
  const ctx = useContext(WeaveflowRouteContext);
  return ctx;
};

export const useWeaveflowCurrentRouteContext = () => {
  const ctx = useContext(WeaveflowRouteContext);
  const {isPeeking} = useContext(WeaveflowPeekContext);
  return isPeeking ? ctx.peekingRouter : ctx.baseRouter;
};

export const Browse3WeaveflowRouteContextProvider = ({
  projectRoot,
  children,
}: {
  children: ReactNode;
  projectRoot(entityName: string, projectName: string): string;
}) => {
  const baseRouter = browse3ContextGen(projectRoot);
  return (
    <WeaveflowRouteContext.Provider
      value={{baseRouter, peekingRouter: useMakePeekingRouter()}}>
      {children}
    </WeaveflowRouteContext.Provider>
  );
};

type WFDBTableType =
  | 'Op'
  | 'OpVersion'
  | 'Type'
  | 'TypeVersion'
  | 'Trace'
  | 'Call'
  | 'Object'
  | 'ObjectVersion';
export const browse2Context = {
  refUIUrl: (
    rootTypeName: string,
    objRef: ObjectRef,
    wfTable?: WFDBTableType
  ) => {
    if (!isWandbArtifactRef(objRef)) {
      throw new Error('Not a wandb artifact ref: ' + JSON.stringify(objRef));
    }
    return `/${objRef.entityName}/${objRef.projectName}/${rootTypeName}/${objRef.artifactName}/${objRef.artifactVersion}`;
  },
  entityUrl: (entityName: string) => {
    return `/${entityName}`;
  },
  projectUrl: (entityName: string, projectName: string) => {
    return `/${entityName}/${projectName}`;
  },
  callUIUrl: (
    entityName: string,
    projectName: string,
    traceId: string,
    callId: string,
    descendentCallId?: string,
    hideTraceTree?: boolean,
    showFeedback?: boolean
  ) => {
    return `/${entityName}/${projectName}/trace/${traceId}/${callId}`;
  },
  typeUIUrl: (entityName: string, projectName: string, typeName: string) => {
    throw new Error('Not implemented');
  },
  objectUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string
  ) => {
    throw new Error('Not implemented');
  },
  opUIUrl: (entityName: string, projectName: string, opName: string) => {
    throw new Error('Not implemented');
  },
  objectVersionUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string,
    objectVersionHash: string,
    filePath?: string,
    refExtra?: string
  ) => {
    throw new Error('Not implemented');
  },
  opVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelOpVersionFilter
  ) => {
    throw new Error('Not implemented');
  },
  opVersionUIUrl: (
    entityName: string,
    projectName: string,
    opName: string,
    opVersionHash: string
  ) => {
    return `/${entityName}/${projectName}/OpDef/${opName}/${opVersionHash}`;
  },
  tracesUIUrl: (entityName: string, projectName: string) => {
    throw new Error('Not implemented');
  },
  callsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelCallFilter,
    gridFilters?: GridFilterModel
  ) => {
    throw new Error('Not implemented');
  },
  objectVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelObjectVersionFilter
  ) => {
    throw new Error('Not implemented');
  },
  opPageUrl: (opUri: string) => {
    const parsed = parseRef(opUri);
    if (!isWandbArtifactRef(parsed)) {
      throw new Error('non wandb artifact ref not yet handled');
    }
    return browse2Context.opVersionUIUrl(
      parsed.entityName,
      parsed.projectName,
      parsed.artifactName,
      parsed.artifactVersion
    );
  },
  boardsUIUrl: (entityName: string, projectName: string) => {
    throw new Error('Not implemented');
  },
  tablesUIUrl: (entityName: string, projectName: string) => {
    throw new Error('Not implemented');
  },
  boardForExpressionUIUrl: (
    entityName: string,
    projectName: string,
    expression: string
  ) => {
    throw new Error('Not implemented');
  },
  compareEvaluationsUri: (
    entityName: string,
    projectName: string,
    evaluationCallIds: string[],
    metrics: Record<string, boolean> | null
  ) => {
    throw new Error('Not implemented');
  },

  scorersUIUrl: (entityName: string, projectName: string) => {
    throw new Error('Not implemented');
  },
  leaderboardsUIUrl: (
    entityName: string,
    projectName: string,
    leaderboardName?: string,
    edit?: boolean
  ) => {
    throw new Error('Not implemented');
  },
  compareCallsUri: (
    entityName: string,
    projectName: string,
    callIds: string[]
  ) => {
    throw new Error('Not implemented');
  },
  compareObjectsUri: (
    entityName: string,
    projectName: string,
    objectSpecifiers: string[]
  ) => {
    throw new Error('Not implemented');
  },
};

export const browse3ContextGen = (
  projectRoot: (entityName: string, projectName: string) => string
) => {
  const browse3Context = {
    refUIUrl: (
      rootTypeName: string,
      objRef: ObjectRef,
      wfTable?: WFDBTableType
    ) => {
      if (!isWandbArtifactRef(objRef) && !isWeaveObjectRef(objRef)) {
        throw new Error('Not a wandb artifact ref: ' + JSON.stringify(objRef));
      }
      if (wfTable === 'OpVersion' || rootTypeName === 'OpDef') {
        return browse3Context.opVersionUIUrl(
          objRef.entityName,
          objRef.projectName,
          objRef.artifactName,
          objRef.artifactVersion
        );
      }

      // TEMP HACK (Tim): This is a temp hack to handle old URIs logged with
      // weave client before having landed and deployed
      // https://github.com/wandb/weave/pull/1169. Should be removed before the
      // public release.
      if (isWandbArtifactRef(objRef)) {
        if (objRef.artifactPath.endsWith('rows%2F0')) {
          objRef.artifactPath = 'obj';
          let newArtifactRefExtra = `${OBJECT_ATTR_EDGE_NAME}/rows`;
          objRef.artifactRefExtra?.split('/').forEach(part => {
            if (isNaN(parseInt(part, 10))) {
              newArtifactRefExtra += `/${DICT_KEY_EDGE_NAME}/` + part;
            } else {
              newArtifactRefExtra += `/${AWL_ROW_EDGE_NAME}/` + part;
            }
          });
          objRef.artifactRefExtra = newArtifactRefExtra;
        }
      }

      if (isWandbArtifactRef(objRef)) {
        return browse3Context.objectVersionUIUrl(
          objRef.entityName,
          objRef.projectName,
          objRef.artifactName,
          objRef.artifactVersion,
          objRef.artifactPath,
          objRef.artifactRefExtra
        );
      } else if (isWeaveObjectRef(objRef)) {
        return browse3Context.objectVersionUIUrl(
          objRef.entityName,
          objRef.projectName,
          objRef.artifactName,
          objRef.artifactVersion,
          undefined,
          objRef.artifactRefExtra
        );
      }
      throw new Error('Unknown ref type');
    },
    entityUrl: (entityName: string) => {
      return `/${entityName}`;
    },
    projectUrl: (entityName: string, projectName: string) => {
      return `${projectRoot(entityName, projectName)}`;
    },
    typeUIUrl: (entityName: string, projectName: string, typeName: string) => {
      return `${projectRoot(entityName, projectName)}/types/${typeName}`;
    },
    objectUIUrl: (
      entityName: string,
      projectName: string,
      objectName: string
    ) => {
      return `${projectRoot(entityName, projectName)}/objects/${objectName}`;
    },
    opUIUrl: (entityName: string, projectName: string, opName: string) => {
      return `${projectRoot(entityName, projectName)}/ops/${opName}`;
    },
    objectVersionUIUrl: (
      entityName: string,
      projectName: string,
      objectName: string,
      objectVersionHash: string,
      filePath?: string,
      refExtra?: string
    ) => {
      const path = filePath ? `path=${encodeURIComponent(filePath)}` : '';
      const extra = refExtra ? `extra=${encodeURIComponent(refExtra)}` : '';

      return `${projectRoot(
        entityName,
        projectName
      )}/objects/${objectName}/versions/${objectVersionHash}?${path}&${extra}`;
    },
    opVersionsUIUrl: (
      entityName: string,
      projectName: string,
      filter?: WFHighLevelOpVersionFilter
    ) => {
      const prunedFilter = pruneEmptyFields(filter);
      if (Object.keys(prunedFilter).length === 0) {
        return `${projectRoot(entityName, projectName)}/op-versions`;
      }
      return `${projectRoot(
        entityName,
        projectName
      )}/op-versions?filter=${encodeURIComponent(
        JSON.stringify(prunedFilter)
      )}`;
    },
    opVersionUIUrl: (
      entityName: string,
      projectName: string,
      opName: string,
      opVersionHash: string
    ) => {
      return `${projectRoot(
        entityName,
        projectName
      )}/ops/${opName}/versions/${opVersionHash}`;
    },
    callUIUrl: (
      entityName: string,
      projectName: string,
      traceId: string,
      callId: string,
      descendentCallId?: string,
      hideTraceTree?: boolean,
      showFeedback?: boolean
    ) => {
      let url = `${projectRoot(entityName, projectName)}/calls/${callId}`;
      const params = new URLSearchParams();
      if (descendentCallId) {
        params.set(DESCENDENT_CALL_ID_PARAM, descendentCallId);
      }
      if (hideTraceTree !== undefined) {
        params.set(HIDE_TRACETREE_PARAM, hideTraceTree ? '1' : '0');
      }
      if (showFeedback !== undefined) {
        params.set(SHOW_FEEDBACK_PARAM, showFeedback ? '1' : '0');
      }
      if (params.toString()) {
        url += '?' + params.toString();
      }
      return url;
    },
    tracesUIUrl: (entityName: string, projectName: string) => {
      return `${projectRoot(entityName, projectName)}/traces`;
    },
    callsUIUrl: (
      entityName: string,
      projectName: string,
      filter?: WFHighLevelCallFilter,
      gridFilters?: GridFilterModel
    ) => {
      const searchParams = new URLSearchParams();
      const prunedFilter = pruneEmptyFields(filter);
      if (Object.keys(prunedFilter).length !== 0) {
        searchParams.set('filter', JSON.stringify(prunedFilter));
      }
      if (gridFilters) {
        searchParams.set('filters', JSON.stringify(gridFilters));
      }
      return `${projectRoot(
        entityName,
        projectName
      )}/traces?${searchParams.toString()}`;
    },
    objectVersionsUIUrl: (
      entityName: string,
      projectName: string,
      filter?: WFHighLevelObjectVersionFilter
    ) => {
      const prunedFilter = pruneEmptyFields(filter);
      if (Object.keys(prunedFilter).length === 0) {
        return `${projectRoot(entityName, projectName)}/object-versions`;
      }
      return `${projectRoot(
        entityName,
        projectName
      )}/object-versions?filter=${encodeURIComponent(
        JSON.stringify(prunedFilter)
      )}`;
    },
    opPageUrl: (opUri: string) => {
      const parsed = parseRef(opUri);
      if (!isWandbArtifactRef(parsed)) {
        throw new Error('non wandb artifact ref not yet handled');
      }
      return browse3Context.opVersionUIUrl(
        parsed.entityName,
        parsed.projectName,
        parsed.artifactName,
        parsed.artifactVersion
      );
    },
    boardsUIUrl: (entityName: string, projectName: string) => {
      return `${projectRoot(entityName, projectName)}/boards`;
    },
    tablesUIUrl: (entityName: string, projectName: string) => {
      return `${projectRoot(entityName, projectName)}/tables`;
    },
    boardForExpressionUIUrl: (
      entityName: string,
      projectName: string,
      expression: string
    ) => {
      // TODO: This is totally wrong and needs to be updated
      // when we have a proper boards page. Note, when that
      // is the case, we should not be asking the user for
      // an expression most likely.
      let base = 'https://weave.wandb.ai';
      console.log(window); // https://app.wandb.test/
      if (window.location.host === 'app.wandb.test') {
        base = 'https://weave.wandb.test';
      }
      return `${base}/?exp=${encodeURIComponent(expression)}`;
    },
    compareEvaluationsUri: (
      entityName: string,
      projectName: string,
      evaluationCallIds: string[],
      metrics: Record<string, boolean> | null
    ) => {
      const metricsPart = metrics
        ? `&metrics=${encodeURIComponent(JSON.stringify(metrics))}`
        : '';
      return `${projectRoot(
        entityName,
        projectName
      )}/compare-evaluations?evaluationCallIds=${encodeURIComponent(
        JSON.stringify(evaluationCallIds)
      )}${metricsPart}`;
    },

    scorersUIUrl: (entityName: string, projectName: string) => {
      return `${projectRoot(entityName, projectName)}/scorers`;
    },

    leaderboardsUIUrl: (
      entityName: string,
      projectName: string,
      leaderboardName?: string,
      edit?: boolean
    ) => {
      return `${projectRoot(entityName, projectName)}/leaderboards${
        leaderboardName ? `/${leaderboardName}` : ''
      }${edit ? '?edit=true' : ''}`;
    },
    compareCallsUri: (
      entityName: string,
      projectName: string,
      callIds: string[]
    ) => {
      const params = callIds
        .map(id => 'call=' + encodeURIComponent(id))
        .join('&');
      return `${projectRoot(entityName, projectName)}/compare?${params}`;
    },
    compareObjectsUri: (
      entityName: string,
      projectName: string,
      objectSpecifiers: string[]
    ) => {
      const params = objectSpecifiers
        .map(id => 'obj=' + encodeURIComponent(id))
        .join('&');
      return `${projectRoot(entityName, projectName)}/compare?${params}`;
    },
  };
  return browse3Context;
};

type RouteType = {
  refUIUrl: (
    rootTypeName: string,
    objRef: ObjectRef,
    wfTable?: WFDBTableType
  ) => string;
  entityUrl: (entityName: string) => string;
  projectUrl: (entityName: string, projectName: string) => string;
  typeUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string
  ) => string;
  objectUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string
  ) => string;
  opUIUrl: (entityName: string, projectName: string, opName: string) => string;
  objectVersionUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string,
    objectVersionHash: string,
    filePath?: string,
    refExtra?: string
  ) => string;
  opVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelOpVersionFilter
  ) => string;
  opVersionUIUrl: (
    entityName: string,
    projectName: string,
    opName: string,
    opVersionHash: string
  ) => string;
  callUIUrl: (
    entityName: string,
    projectName: string,
    traceId: string,
    callId: string,
    descendentCallId?: string,
    hideTraceTree?: boolean,
    showFeedback?: boolean
  ) => string;
  tracesUIUrl: (entityName: string, projectName: string) => string;
  callsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelCallFilter,
    // Using GridFilterModel here is really bad. Somehow this leaked into
    // the implementation and now it is a part of our URL spec forever... :(
    // It should have been implemented as the `query` component of WFHighLevelCallFilter
    // which maps to our actual service API.
    gridFilters?: GridFilterModel
  ) => string;
  objectVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelObjectVersionFilter
  ) => string;
  boardsUIUrl: (
    entityName: string,
    projectName: string
    // TODO: Add filter when supported
  ) => string;
  boardForExpressionUIUrl: (
    entityName: string,
    projectName: string,
    expression: string
    // TODO: Add filter when supported
  ) => string;
  tablesUIUrl: (
    entityName: string,
    projectName: string
    // TODO: Add filter when supported
  ) => string;
  opPageUrl: (opUri: string) => string;
  compareEvaluationsUri: (
    entityName: string,
    projectName: string,
    evaluationCallIds: string[],
    metrics: Record<string, boolean> | null
  ) => string;

  scorersUIUrl: (entityName: string, projectName: string) => string;

  leaderboardsUIUrl: (
    entityName: string,
    projectName: string,
    leaderboardName?: string,
    edit?: boolean
  ) => string;
  compareCallsUri: (
    entityName: string,
    projectName: string,
    callIds: string[]
  ) => string;
  compareObjectsUri: (
    entityName: string,
    projectName: string,
    objectSpecifiers: string[]
  ) => string;
};

const useSetSearchParam = () => {
  const location = useLocation();
  return useCallback(
    (key: string, value: string | null) => {
      const searchParams = new URLSearchParams(location.search);
      if (value === null) {
        searchParams.delete(key);
      } else {
        searchParams.set(key, value);
      }
      const newSearch = searchParams.toString();
      const newUrl = `${location.pathname}?${newSearch}`;
      return newUrl;
    },
    [location]
  );
};

export const PEEK_PARAM = 'peekPath';
export const HIDE_TRACETREE_PARAM = 'hideTraceTree';
export const SHOW_FEEDBACK_PARAM = 'showFeedback';
export const DESCENDENT_CALL_ID_PARAM = 'descendentCallId';

export const baseContext = browse3ContextGen(
  (entityName: string, projectName: string) => {
    return `/${entityName}/${projectName}`;
  }
);

const useMakePeekingRouter = (): RouteType => {
  const setSearchParam = useSetSearchParam();

  return {
    refUIUrl: (...args: Parameters<typeof baseContext.refUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.refUIUrl(...args));
    },
    entityUrl: (...args: Parameters<typeof baseContext.entityUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.entityUrl(...args));
    },
    projectUrl: (...args: Parameters<typeof baseContext.projectUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.projectUrl(...args));
    },
    typeUIUrl: (...args: Parameters<typeof baseContext.typeUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.typeUIUrl(...args));
    },
    objectUIUrl: (...args: Parameters<typeof baseContext.objectUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.objectUIUrl(...args));
    },
    opUIUrl: (...args: Parameters<typeof baseContext.opUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.opUIUrl(...args));
    },
    objectVersionUIUrl: (
      ...args: Parameters<typeof baseContext.objectVersionUIUrl>
    ) => {
      return setSearchParam(
        PEEK_PARAM,
        baseContext.objectVersionUIUrl(...args)
      );
    },
    opVersionsUIUrl: (
      ...args: Parameters<typeof baseContext.opVersionsUIUrl>
    ) => {
      return setSearchParam(PEEK_PARAM, baseContext.opVersionsUIUrl(...args));
    },
    opVersionUIUrl: (
      ...args: Parameters<typeof baseContext.opVersionUIUrl>
    ) => {
      return setSearchParam(PEEK_PARAM, baseContext.opVersionUIUrl(...args));
    },
    callUIUrl: (...args: Parameters<typeof baseContext.callUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.callUIUrl(...args));
    },
    tracesUIUrl: (...args: Parameters<typeof baseContext.tracesUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.tracesUIUrl(...args));
    },
    callsUIUrl: (...args: Parameters<typeof baseContext.callsUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.callsUIUrl(...args));
    },
    objectVersionsUIUrl: (
      ...args: Parameters<typeof baseContext.objectVersionsUIUrl>
    ) => {
      return setSearchParam(
        PEEK_PARAM,
        baseContext.objectVersionsUIUrl(...args)
      );
    },
    opPageUrl: (...args: Parameters<typeof baseContext.opPageUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.opPageUrl(...args));
    },
    boardsUIUrl: (...args: Parameters<typeof baseContext.boardsUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.boardsUIUrl(...args));
    },
    tablesUIUrl: (...args: Parameters<typeof baseContext.tablesUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.tablesUIUrl(...args));
    },
    boardForExpressionUIUrl: (
      ...args: Parameters<typeof baseContext.boardForExpressionUIUrl>
    ) => {
      throw new Error('Not implemented');
      // return setSearchParam(
      //   PEEK_PARAM,
      //   baseContext.boardForExpressionUIUrl(...args)
      // );
    },
    compareEvaluationsUri: (
      ...args: Parameters<typeof baseContext.compareEvaluationsUri>
    ) => {
      return setSearchParam(
        PEEK_PARAM,
        baseContext.compareEvaluationsUri(...args)
      );
    },
    scorersUIUrl: (...args: Parameters<typeof baseContext.scorersUIUrl>) => {
      return setSearchParam(PEEK_PARAM, baseContext.scorersUIUrl(...args));
    },
    leaderboardsUIUrl: (
      ...args: Parameters<typeof baseContext.leaderboardsUIUrl>
    ) => {
      return setSearchParam(PEEK_PARAM, baseContext.leaderboardsUIUrl(...args));
    },
    compareCallsUri: (
      ...args: Parameters<typeof baseContext.compareCallsUri>
    ) => {
      return setSearchParam(PEEK_PARAM, baseContext.compareCallsUri(...args));
    },
    compareObjectsUri: (
      ...args: Parameters<typeof baseContext.compareObjectsUri>
    ) => {
      return setSearchParam(PEEK_PARAM, baseContext.compareObjectsUri(...args));
    },
  };
};

const WeaveflowRouteContext = createContext<{
  baseRouter: RouteType;
  peekingRouter: RouteType;
}>({
  baseRouter: browse2Context,
  peekingRouter: browse2Context,
});

export const WeaveflowPeekContext = createContext<{
  isPeeking?: boolean;
}>({
  isPeeking: false,
});

export const useClosePeek = () => {
  const history = useHistory();
  return () => {
    const queryParams = new URLSearchParams(history.location.search);
    if (queryParams.has(PEEK_PARAM)) {
      queryParams.delete(PEEK_PARAM);
      history.replace({
        search: queryParams.toString(),
      });
    }
  };
};

export const usePeekLocation = () => {
  const {peekPath} = useURLSearchParamsDict();

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

export const WeaveHeaderExtrasContext = createContext<{
  extras: {[key: string]: HeaderExtra};
  addExtra: (key: string, value: HeaderExtra) => void;
  removeExtra: (key: string) => void;
  renderExtras: () => ReactNode;
}>({
  extras: {},
  addExtra: () => {},
  removeExtra: () => {},
  renderExtras: () => null,
});

export const FeedbackContext = createContext<{
  showFeedback?: boolean;
  setShowFeedback: (showFeedback: boolean | undefined) => void;
}>({
  showFeedback: undefined,
  setShowFeedback: () => {},
});

export const useFeedbackContext = () => {
  return useContext(FeedbackContext);
};

type HeaderExtra = {node: ReactNode; order?: number};

export const WeaveHeaderExtrasProvider = ({
  children,
}: {
  children: ReactNode;
}) => {
  const [extras, setExtras] = useState<{[key: string]: HeaderExtra}>({});
  const addExtra = useCallback(
    (key: string, extra: HeaderExtra) => {
      setExtras(prev => {
        return {...prev, [key]: extra};
      });
    },
    [setExtras]
  );

  const removeExtra = useCallback(
    (key: string) => {
      setExtras(prev => {
        const newExtras = {...prev};
        delete newExtras[key];
        return newExtras;
      });
    },
    [setExtras]
  );

  const renderExtras = useCallback(() => {
    return (
      <>
        {Object.entries(extras)
          .sort((a, b) => (a[1].order || 0) - (b[1].order || 0))
          .map(([key, extra]) => {
            return <React.Fragment key={key}>{extra.node}</React.Fragment>;
          })}
      </>
    );
  }, [extras]);

  return (
    <WeaveHeaderExtrasContext.Provider
      value={{extras, addExtra, removeExtra, renderExtras}}>
      {children}
    </WeaveHeaderExtrasContext.Provider>
  );
};

export const FeedbackProvider = ({
  children,
  initialShowFeedback,
  setShowFeedbackInUrl,
}: {
  children: ReactNode;
  initialShowFeedback?: boolean;
  setShowFeedbackInUrl: (showFeedback: boolean | undefined) => void;
}) => {
  const [showFeedback, setShowFeedbackState] = useState<boolean | undefined>(
    initialShowFeedback
  );

  const setShowFeedback = useCallback(
    (value: boolean | undefined) => {
      setShowFeedbackState(value);
      setShowFeedbackInUrl(value);
    },
    [setShowFeedbackInUrl]
  );

  return (
    <FeedbackContext.Provider value={{showFeedback, setShowFeedback}}>
      {children}
    </FeedbackContext.Provider>
  );
};
