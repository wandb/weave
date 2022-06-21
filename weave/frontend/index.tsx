import React, {
  useMemo,
  useCallback,
  useState,
  useEffect,
  Suspense,
} from 'react';
import ReactDOM from 'react-dom';

import {createRemoteClient} from '@wandb/cg/browser';
import PanelPage from './components/PagePanel';

import {backendWeaveUrl} from '@wandb/common/config';

import makeComp from '@wandb/common/util/profiler';
import './globalStyleImports';
import ClientContext from '@wandb/common/cgreact.ClientContext';
import WeaveAppContext, {
  WeaveAppState,
} from '@wandb/common/cgreact.WeaveAppContext';
import BasicNoMatchComponent from '@wandb/common/components/BasicNoMatchComponent';

const ComputeGraphContextProvider: React.FC = makeComp(
  ({children}) => {
    const cgClient = useMemo(
      () => createRemoteClient(backendWeaveUrl(), async () => undefined, false),
      []
    );
    const [mutationId, setMutationId] = useState(0);
    const incMutationId = useCallback(
      () => setMutationId(mutationId + 1),
      [mutationId]
    );
    const context = useMemo(
      () => ({client: cgClient, mutationId, incMutationId}),
      [cgClient, mutationId, incMutationId]
    );

    const [isLoading, setIsLoading] = useState(false);
    useEffect(() => {
      const subscription = context.client
        .loadingObservable()
        .subscribe(setIsLoading);
      return () => subscription.unsubscribe();
    }, [context]);

    const appState = useMemo(
      () => ({
        'weave-backend': true,
        'weave-plot': false,
        'weave-devpopup': false,
        'instant replay': false,
        'unicorn-plot': false,
        'model-registry': false,
        'lazy-table': false,
        'model-registry-advanced': false,
        'artifact-portfolios': false,
        noMatchComponentType: BasicNoMatchComponent,
      }),
      []
    );

    return (
      <div
        data-test="compute-graph-provider"
        className={isLoading ? 'loading cg-executing' : ''}>
        <WeaveAppContext.Provider value={appState}>
          <ClientContext.Provider value={context}>
            {children}
          </ClientContext.Provider>
        </WeaveAppContext.Provider>
      </div>
    );
  },
  {id: 'ComputeGraphContextProvider', memo: true}
);

ReactDOM.render(
  <React.Suspense fallback={'loading'}>
    <ComputeGraphContextProvider>
      <PanelPage />
    </ComputeGraphContextProvider>
  </React.Suspense>,
  document.getElementById('root')
);
