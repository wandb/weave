import React, {
  createContext,
  FC,
  useCallback,
  useContext,
  useMemo,
} from 'react';

import {TraceServerClient} from './traceServerClient';

const TraceServerClientContext = createContext<TraceServerClient | null>(null);

export const useHasTraceServerClientContext = () => {
  const ctx = useContext(TraceServerClientContext);
  return ctx !== null;
};

export const useGetTraceServerClientContext = () => {
  const ctx = useContext(TraceServerClientContext);
  return useCallback(() => {
    if (ctx === null) {
      throw new Error('No TraceServerClientContext');
    }
    return ctx;
  }, [ctx]);
};

const TraceServerClientContextProvider: FC<{
  baseUrl: string;
}> = ({baseUrl, children}) => {
  const client = useMemo(() => {
    return new TraceServerClient(baseUrl);
  }, [baseUrl]);
  return (
    <TraceServerClientContext.Provider value={client}>
      {children}
    </TraceServerClientContext.Provider>
  );
};

export const OptionalTraceServerClientFromWindowConfigProvider: FC = ({
  children,
}) => {
  // This is pretty hacky. Essentially if we are mounted in the core app, then we will have
  // a trace backend url provided by the window.CONFIG. This is populated by the core app frontend
  // build process. However, if we are in a self-hosted weave environment, then the entrypoint will
  // load up the env variables dynamically fom the weave server and populate the window.WEAVE_CONFIG.
  //
  // Our primary use case is the app running in the core app, so we will use the window.CONFIG if it is
  // available. If it is not, then we will use the window.WEAVE_CONFIG.
  const traceBackendBaseUrlProvidedByWandbServer = (window as any).CONFIG
    ?.TRACE_BACKEND_BASE_URL;
  const traceBackendBaseUrlProvidedByWeaveServer = (window as any).WEAVE_CONFIG
    ?.TRACE_BACKEND_BASE_URL;

  if (
    traceBackendBaseUrlProvidedByWandbServer != null &&
    traceBackendBaseUrlProvidedByWandbServer !== ''
  ) {
    return (
      <TraceServerClientContextProvider
        baseUrl={traceBackendBaseUrlProvidedByWandbServer}>
        {children}
      </TraceServerClientContextProvider>
    );
  } else if (
    traceBackendBaseUrlProvidedByWeaveServer != null &&
    traceBackendBaseUrlProvidedByWeaveServer !== ''
  ) {
    return (
      <TraceServerClientContextProvider
        baseUrl={traceBackendBaseUrlProvidedByWeaveServer}>
        {children}
      </TraceServerClientContextProvider>
    );
  }
  return <>{children}</>;
};
