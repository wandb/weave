import {ArtifactRef, isWandbArtifactRef, parseRef} from '@wandb/weave/react';
import _ from 'lodash';
import React, {createContext, useContext} from 'react';

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

export const Browse3WeaveflowRouteContextProvider = ({
  projectRoot,
  children,
}: {
  projectRoot(entityName: string, projectName: string): string;
  children: React.ReactNode;
}) => {
  return (
    <WeaveflowRouteContext.Provider value={browse3ContextGen(projectRoot)}>
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
const browse2Context = {
  refUIUrl: (
    rootTypeName: string,
    objRef: ArtifactRef,
    wfTable?: WFDBTableType
  ) => {
    if (!isWandbArtifactRef(objRef)) {
      throw new Error('Not a wandb artifact ref');
    }
    return `/${objRef.entityName}/${objRef.projectName}/${rootTypeName}/${objRef.artifactName}/${objRef.artifactVersion}`;
  },
  entityUrl: (entityName: string) => {
    return `/${entityName}`;
  },
  projectUrl: (entityName: string, projectName: string) => {
    return `${projectRoot(entityName, projectName)}`;
  },
  callUIUrl: (
    entityName: string,
    projectName: string,
    traceId: string,
    callId: string
  ) => {
    return `${projectRoot(entityName, projectName)}/trace/${traceId}/${callId}`;
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
    return `${projectRoot(
      entityName,
      projectName
    )}/OpDef/${opName}/${opVersionHash}`;
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
        throw new Error('Not a wandb artifact ref');
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
  opPageUrl: (opUri: string) => string;
};
const WeaveflowRouteContext = createContext<RouteType>(browse2Context);
