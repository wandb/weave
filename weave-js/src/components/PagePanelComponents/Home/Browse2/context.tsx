import {ArtifactRef, isWandbArtifactRef, parseRef} from '@wandb/weave/react';
import React, {createContext, useContext} from 'react';

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
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
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
  opVersionUIUrl: (
    entityName: string,
    projectName: string,
    opName: string,
    opVersionHash: string
  ) => {
    return `/${entityName}/${projectName}/OpDef/${opName}/${opVersionHash}`;
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
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
  ) => {
    return `/${entityName}/${projectName}/types/${typeName}/versions/${typeVersionHash}`;
  },
  objectVersionUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string,
    objectVersionHash: string
  ) => {
    return `/${entityName}/${projectName}/objects/${objectName}/versions/${objectVersionHash}`;
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
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
  ) => string;
  objectVersionUIUrl: (
    entityName: string,
    projectName: string,
    objectName: string,
    objectVersionHash: string
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
  opPageUrl: (opUri: string) => string;
}>(defaultContext);
