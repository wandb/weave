import React, {createContext, useContext} from 'react';

import {WFProject} from './types';

type WeaveflowORMContextType = {
  projectConnection: WFProject;
};

const WeaveflowORMContext = createContext<WeaveflowORMContextType | null>(null);

export const useWeaveflowORMContext = () => {
  const ctx = useContext(WeaveflowORMContext);
  if (ctx == null) {
    throw new Error('No WeaveflowORMContext');
  }
  return ctx;
};

export const WeaveflowORMContextProvider = ({
  children,
  projectConnection,
}: {
  children: React.ReactNode;
  projectConnection: WFProject;
}) => {
  const value = React.useMemo(() => {
    return {
      projectConnection,
    };
  }, [projectConnection]);
  return (
    <WeaveflowORMContext.Provider value={value}>
      {children}
    </WeaveflowORMContext.Provider>
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
