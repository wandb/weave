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

const defaultContext = {
  refUIUrl: (rootTypeName: string, objRef: ArtifactRef) => {
    if (!isWandbArtifactRef(objRef)) {
      throw new Error('Not a wandb artifact ref');
    }
    return `/${objRef.entityName}/${objRef.projectName}/${rootTypeName}/${objRef.artifactName}/${objRef.artifactVersion}`;
  },
};

const newContext = {
  refUIUrl: (rootTypeName: string, objRef: ArtifactRef) => {
    if (!isWandbArtifactRef(objRef)) {
      throw new Error('Not a wandb artifact ref');
    }
    // TODO: Redirect to correct urls
    return `/${objRef.entityName}/${objRef.projectName}/objects/${objRef.artifactName}/versions/${objRef.artifactVersion}`;
  },
};

const WeaveflowRouteContext = createContext<{
  refUIUrl: (rootTypeName: string, objRef: ArtifactRef) => string;
}>(defaultContext);
