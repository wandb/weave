import {ArtifactRef, isWandbArtifactRef, parseRef} from '@wandb/weave/react';
import _ from 'lodash';
import React, {createContext, useCallback, useContext} from 'react';
import {useLocation} from 'react-router-dom';

import {WFHighLevelCallFilter} from './pages/CallsPage';
import {WFHighLevelObjectVersionFilter} from './pages/ObjectVersionsPage';
import {WFHighLevelOpVersionFilter} from './pages/OpVersionsPage';
import {WFHighLevelTypeVersionFilter} from './pages/TypeVersionsPage';

const pruneEmptyFields = (filter: {[key: string]: any} | null | undefined) => {
  if (!filter) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(filter).filter(
      ([k, v]) =>
        v != null &&
        v !== undefined &&
        v !== false &&
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
  children: React.ReactNode;
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
    objRef: ArtifactRef,
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
    callId: string
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
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
  ) => {
    throw new Error('Not implemented');
  },
  typeVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelTypeVersionFilter
  ) => {
    throw new Error('Not implemented');
  },
  objectVersionUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string,
    objectVersionHash: string
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
  callsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelCallFilter
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
};

const browse3ContextGen = (
  projectRoot: (entityName: string, projectName: string) => string
) => {
  const browse3Context = {
    refUIUrl: (
      rootTypeName: string,
      objRef: ArtifactRef,
      wfTable?: WFDBTableType
    ) => {
      if (!isWandbArtifactRef(objRef)) {
        throw new Error('Not a wandb artifact ref: ' + JSON.stringify(objRef));
      }
      if (wfTable === 'OpVersion' || rootTypeName === 'OpDef') {
        return browse3Context.opVersionUIUrl(
          objRef.entityName,
          objRef.projectName,
          objRef.artifactName,
          objRef.artifactVersion
        );
      } else if (wfTable === 'TypeVersion' || rootTypeName === 'type') {
        return browse3Context.typeVersionUIUrl(
          objRef.entityName,
          objRef.projectName,
          objRef.artifactName,
          objRef.artifactVersion
        );
      }
      return browse3Context.objectVersionUIUrl(
        objRef.entityName,
        objRef.projectName,
        objRef.artifactName,
        objRef.artifactVersion
      );
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
    typeVersionUIUrl: (
      entityName: string,
      projectName: string,
      typeName: string,
      typeVersionHash: string
    ) => {
      return `${projectRoot(
        entityName,
        projectName
      )}/types/${typeName}/versions/${typeVersionHash}`;
    },
    typeVersionsUIUrl: (
      entityName: string,
      projectName: string,
      filter?: WFHighLevelTypeVersionFilter
    ) => {
      const prunedFilter = pruneEmptyFields(filter);
      if (Object.keys(prunedFilter).length === 0) {
        return `${projectRoot(entityName, projectName)}/type-versions`;
      }

      return `${projectRoot(
        entityName,
        projectName
      )}/type-versions?filter=${encodeURIComponent(
        JSON.stringify(prunedFilter)
      )}`;
    },
    objectVersionUIUrl: (
      entityName: string,
      projectName: string,
      objectName: string,
      objectVersionHash: string
    ) => {
      return `${projectRoot(
        entityName,
        projectName
      )}/objects/${objectName}/versions/${objectVersionHash}`;
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
      callId: string
    ) => {
      return `${projectRoot(entityName, projectName)}/calls/${callId}`;
    },
    callsUIUrl: (
      entityName: string,
      projectName: string,
      filter?: WFHighLevelCallFilter
    ) => {
      const prunedFilter = pruneEmptyFields(filter);
      if (Object.keys(prunedFilter).length === 0) {
        return `${projectRoot(entityName, projectName)}/calls`;
      }
      return `${projectRoot(
        entityName,
        projectName
      )}/calls?filter=${encodeURIComponent(JSON.stringify(prunedFilter))}`;
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
  };
  return browse3Context;
};

type RouteType = {
  refUIUrl: (
    rootTypeName: string,
    objRef: ArtifactRef,
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
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
  ) => string;
  typeVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelTypeVersionFilter
  ) => string;
  objectVersionUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string,
    objectVersionHash: string
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
    callId: string
  ) => string;
  callsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelCallFilter
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

const PEAK_SEARCH_PARAM = 'peekPath';
export const baseContext = browse3ContextGen(
  (entityName: string, projectName: string) => {
    return `/${entityName}/${projectName}`;
  }
);

const useMakePeekingRouter = (): RouteType => {
  const setSearchParam = useSetSearchParam();

  return {
    refUIUrl: (...args: Parameters<typeof baseContext.refUIUrl>) => {
      return setSearchParam(PEAK_SEARCH_PARAM, baseContext.refUIUrl(...args));
    },
    entityUrl: (...args: Parameters<typeof baseContext.entityUrl>) => {
      return setSearchParam(PEAK_SEARCH_PARAM, baseContext.entityUrl(...args));
    },
    projectUrl: (...args: Parameters<typeof baseContext.projectUrl>) => {
      return setSearchParam(PEAK_SEARCH_PARAM, baseContext.projectUrl(...args));
    },
    typeUIUrl: (...args: Parameters<typeof baseContext.typeUIUrl>) => {
      return setSearchParam(PEAK_SEARCH_PARAM, baseContext.typeUIUrl(...args));
    },
    objectUIUrl: (...args: Parameters<typeof baseContext.objectUIUrl>) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.objectUIUrl(...args)
      );
    },
    opUIUrl: (...args: Parameters<typeof baseContext.opUIUrl>) => {
      return setSearchParam(PEAK_SEARCH_PARAM, baseContext.opUIUrl(...args));
    },
    typeVersionUIUrl: (
      ...args: Parameters<typeof baseContext.typeVersionUIUrl>
    ) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.typeVersionUIUrl(...args)
      );
    },
    typeVersionsUIUrl: (
      ...args: Parameters<typeof baseContext.typeVersionsUIUrl>
    ) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.typeVersionsUIUrl(...args)
      );
    },
    objectVersionUIUrl: (
      ...args: Parameters<typeof baseContext.objectVersionUIUrl>
    ) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.objectVersionUIUrl(...args)
      );
    },
    opVersionsUIUrl: (
      ...args: Parameters<typeof baseContext.opVersionsUIUrl>
    ) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.opVersionsUIUrl(...args)
      );
    },
    opVersionUIUrl: (
      ...args: Parameters<typeof baseContext.opVersionUIUrl>
    ) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.opVersionUIUrl(...args)
      );
    },
    callUIUrl: (...args: Parameters<typeof baseContext.callUIUrl>) => {
      return setSearchParam(PEAK_SEARCH_PARAM, baseContext.callUIUrl(...args));
    },
    callsUIUrl: (...args: Parameters<typeof baseContext.callsUIUrl>) => {
      return setSearchParam(PEAK_SEARCH_PARAM, baseContext.callsUIUrl(...args));
    },
    objectVersionsUIUrl: (
      ...args: Parameters<typeof baseContext.objectVersionsUIUrl>
    ) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.objectVersionsUIUrl(...args)
      );
    },
    opPageUrl: (...args: Parameters<typeof baseContext.opPageUrl>) => {
      return setSearchParam(PEAK_SEARCH_PARAM, baseContext.opPageUrl(...args));
    },
    boardsUIUrl: (...args: Parameters<typeof baseContext.boardsUIUrl>) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.boardsUIUrl(...args)
      );
    },
    tablesUIUrl: (...args: Parameters<typeof baseContext.tablesUIUrl>) => {
      return setSearchParam(
        PEAK_SEARCH_PARAM,
        baseContext.tablesUIUrl(...args)
      );
    },
    boardForExpressionUIUrl: (
      ...args: Parameters<typeof baseContext.boardForExpressionUIUrl>
    ) => {
      throw new Error('Not implemented');
      // return setSearchParam(
      //   PEAK_SEARCH_PARAM,
      //   baseContext.boardForExpressionUIUrl(...args)
      // );
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
