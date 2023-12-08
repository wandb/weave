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
