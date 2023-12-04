import {ArtifactRef, isWandbArtifactRef} from '@wandb/weave/react';
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
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
  ) => {
    throw new Error('Not implemented');
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
    if (wfTable === 'OpVersion') {
      return `/${objRef.entityName}/${objRef.projectName}/ops/${objRef.artifactName}/versions/${objRef.artifactVersion}`;
    } // } else if (wfTable === 'ObjectVersion') {
    // TODO: Redirect to correct urls
    return `/${objRef.entityName}/${objRef.projectName}/objects/${objRef.artifactName}/versions/${objRef.artifactVersion}`;
  },
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
  ) => {
    return `/${entityName}/${projectName}/types/${typeName}/versions/${typeVersionHash}`;
  },
};

const WeaveflowRouteContext = createContext<{
  refUIUrl: (
    rootTypeName: string,
    objRef: ArtifactRef,
    wfTable?: WFDBTableType
  ) => string;
  typeVersionUIUrl: (
    entityName: string,
    projectName: string,
    typeName: string,
    typeVersionHash: string
  ) => string;
}>(defaultContext);
