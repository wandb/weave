import {ArtifactRef, isWandbArtifactRef, parseRef} from '@wandb/weave/react';
import React, {createContext, useContext} from 'react';

import {WFHighLevelCallFilter} from './pages/CallsPage';
import {WFHighLevelObjectVersionFilter} from './pages/ObjectVersionsPage';
import {WFHighLevelOpVersionFilter} from './pages/OpVersionsPage';
import {WFHighLevelTypeVersionFilter} from './pages/TypeVersionsPage';

export const useWeaveflowRouteContext = () => {
  const ctx = useContext(WeaveflowRouteContext);
  return ctx;
};

export const NewWeaveflowRouteContextProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  return (
    <WeaveflowRouteContext.Provider value={newContext}>
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
const defaultContext = {
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
    return defaultContext.opVersionUIUrl(
      parsed.entityName,
      parsed.projectName,
      parsed.artifactName,
      parsed.artifactVersion
    );
  },
};

const newContext = {
  refUIUrl: (
    rootTypeName: string,
    objRef: ArtifactRef,
    wfTable?: WFDBTableType
  ) => {
    if (!isWandbArtifactRef(objRef)) {
      throw new Error('Not a wandb artifact ref');
    }
    if (wfTable === 'OpVersion' || rootTypeName === 'OpDef') {
      return newContext.opVersionUIUrl(
        objRef.entityName,
        objRef.projectName,
        objRef.artifactName,
        objRef.artifactVersion
      );
    } else if (wfTable === 'TypeVersion' || rootTypeName === 'type') {
      return newContext.typeVersionUIUrl(
        objRef.entityName,
        objRef.projectName,
        objRef.artifactName,
        objRef.artifactVersion
      );
    }
    return newContext.objectVersionUIUrl(
      objRef.entityName,
      objRef.projectName,
      objRef.artifactName,
      objRef.artifactVersion
    );
  },
  typeUIUrl: (entityName: string, projectName: string, typeName: string) => {
    return `/${entityName}/${projectName}/types/${typeName}`;
  },
  objectUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string
  ) => {
    return `/${entityName}/${projectName}/objects/${objectName}`;
  },
  opUIUrl: (entityName: string, projectName: string, opName: string) => {
    return `/${entityName}/${projectName}/ops/${opName}`;
  },
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
  ) => {
    return `/${entityName}/${projectName}/types/${typeName}/versions/${typeVersionHash}`;
  },
  typeVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelTypeVersionFilter
  ) => {
    if (!filter) {
      return `/${entityName}/${projectName}/type-versions`;
    }
    return `/${entityName}/${projectName}/type-versions?filter=${encodeURIComponent(
      JSON.stringify(filter)
    )}`;
  },
  objectVersionUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string,
    objectVersionHash: string
  ) => {
    return `/${entityName}/${projectName}/objects/${objectName}/versions/${objectVersionHash}`;
  },
  opVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelOpVersionFilter
  ) => {
    if (!filter) {
      return `/${entityName}/${projectName}/op-versions`;
    }
    return `/${entityName}/${projectName}/op-versions?filter=${encodeURIComponent(
      JSON.stringify(filter)
    )}`;
  },
  opVersionUIUrl: (
    entityName: string,
    projectName: string,
    opName: string,
    opVersionHash: string
  ) => {
    return `/${entityName}/${projectName}/ops/${opName}/versions/${opVersionHash}`;
  },
  callUIUrl: (
    entityName: string,
    projectName: string,
    traceId: string,
    callId: string
  ) => {
    return `/${entityName}/${projectName}/calls/${callId}`;
  },
  callsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelCallFilter
  ) => {
    if (!filter) {
      return `/${entityName}/${projectName}/calls`;
    }
    return `/${entityName}/${projectName}/calls?filter=${encodeURIComponent(
      JSON.stringify(filter)
    )}`;
  },
  objectVersionsUIUrl: (
    entityName: string,
    projectName: string,
    filter?: WFHighLevelObjectVersionFilter
  ) => {
    if (!filter) {
      return `/${entityName}/${projectName}/object-versions`;
    }
    return `/${entityName}/${projectName}/object-versions?filter=${encodeURIComponent(
      JSON.stringify(filter)
    )}`;
  },
  opPageUrl: (opUri: string) => {
    const parsed = parseRef(opUri);
    if (!isWandbArtifactRef(parsed)) {
      throw new Error('non wandb artifact ref not yet handled');
    }
    return newContext.opVersionUIUrl(
      parsed.entityName,
      parsed.projectName,
      parsed.artifactName,
      parsed.artifactVersion
    );
  },
};

const WeaveflowRouteContext = createContext<{
  refUIUrl: (
    rootTypeName: string,
    objRef: ArtifactRef,
    wfTable?: WFDBTableType
  ) => string;
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
}>(defaultContext);
