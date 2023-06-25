import React, {createContext, PropsWithChildren, useContext} from 'react';

// TODO: probably want to save this as state somewhere?
const registeredContexts = new Map<string, React.Context<any>>(); // TODO: fix any
const createGenericContext = <T extends unknown>(displayName: string) => {
  const newContext = createContext<GenericProviderProps<T>>({
    displayName,
    value: {} as T, // TODO: cheating a little, based on https://stackoverflow.com/a/61336826
  });
  newContext.displayName = displayName;
  registeredContexts.set(displayName, newContext);
  return newContext;
};

const findOrCreateGenericContext = <T extends unknown>(displayName: string) => {
  const existingContext = registeredContexts.get(displayName);
  if (existingContext != null) {
    return existingContext as React.Context<GenericProviderProps<T>>;
  } else {
    return createGenericContext<T>(displayName);
  }
};

type GenericProviderProps<T> = {
  value: T;
  displayName: string;
  allowUndefined?: boolean;
};

export function GenericProvider<T>({
  value,
  displayName,
  allowUndefined = false,
  children,
}: PropsWithChildren<GenericProviderProps<T>>) {
  const GenericContext = findOrCreateGenericContext<T>(displayName);
  return (
    <GenericContext.Provider value={{value, displayName, allowUndefined}}>
      {children}
    </GenericContext.Provider>
  );
}

// TODO: maybe we don't need both T and displayName
export function useGenericContext<T = unknown>({
  displayName,
}: {
  displayName: string;
}) {
  // TODO: we're skipping a null check here...
  const context = registeredContexts.get(displayName) as React.Context<
    GenericProviderProps<T>
  >;
  // const {allowUndefined = false, value} = useContext(
  //   // TODO: is there a smarter way to type this?
  //   GenericContext as React.Context<GenericProviderProps<T>>
  // );
  // const context = findOrCreateGenericContext<T>(displayName);
  // if (context == null) {
  //   return;
  // }
  // TODO: better name. contextValue.value is stupid
  const contextValue = useContext(context);
  const {allowUndefined = false, value} = contextValue;
  // findOrCreateGenericContext<T>(displayName);
  // TODO: change console.log to trace
  // console.log(
  //   'GENERIC',
  //   displayName,
  //   contextValue
  //   // useContext(
  //   //   // TODO: is there a smarter way to type this?
  //   //   // TODO: bug, we overwrite the same context
  //   //   GenericContext as React.Context<GenericProviderProps<T>>
  //   // )
  // );
  // TODO: make error message not generic
  if (value == null && !allowUndefined) {
    throw new Error(
      'useGenericContext must be used inside of a <GenericContextProvider>'
    );
  }
  return value;
}
