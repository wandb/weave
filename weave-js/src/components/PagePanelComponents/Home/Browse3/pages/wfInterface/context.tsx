import React, {createContext, useContext} from 'react';

import {WFProject} from './types';

export type WeaveflowORMContextType = {
  projectConnection: WFProject;
};

const WeaveflowORMContext = createContext<WeaveflowORMContextType | null>(null);

export const useWeaveflowORMContext = (entity: string, project: string) => {
  const ctx = useContext(WeaveflowORMContext);
  if (ctx == null) {
    throw new Error('No WeaveflowORMContext');
  }

  // This is defensive code to make sure that the context is being used
  // correctly.
  if (ctx.projectConnection.entity() !== entity) {
    throw new Error(
      `WeaveflowORMContext entity mismatch, expected ${entity}, got ${ctx.projectConnection.entity()}`
    );
  }
  if (ctx.projectConnection.project() !== project) {
    throw new Error(
      `WeaveflowORMContext project mismatch, expected ${project}, got ${ctx.projectConnection.project()}`
    );
  }
  return ctx;
};

export const useMaybeWeaveflowORMContext = () => {
  const ctx = useContext(WeaveflowORMContext);
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
