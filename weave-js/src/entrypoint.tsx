import './globalStyleImports';

import {ApolloProvider} from '@apollo/client';
import React from 'react';
import ReactDOM from 'react-dom';
import {BrowserRouter as Router, Switch, Route} from 'react-router-dom';
import {StateInspector} from 'reinspect';

import {apolloClient} from './apollo';
import {onAppError} from './components/automation';
import PagePanel from './components/PagePanel';
import {WeaveMessage} from './components/Panel2/WeaveMessage';
import {NotebookComputeGraphContextProvider} from './contextProviders';
import {
  URL_BROWSE,
  URL_LOCAL,
  URL_TEMPLATES,
  URL_RECENT,
  URL_WANDB,
} from './urls';
import getConfig from './config';
import {PanelRootContextProvider} from './components/Panel2/PanelPanel';
import {WeaveViewerContextProvider} from './context/WeaveViewerContext';

class ErrorBoundary extends React.Component<{}, {hasError: boolean}> {
  static getDerivedStateFromError(error: Error) {
    // Update state so the next render will show the fallback UI.
    return {hasError: true};
  }
  constructor(props: {}) {
    super(props);
    this.state = {hasError: false};
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // You can also log the error to an error reporting service
    // logErrorToMyService(error, errorInfo);
    onAppError(
      'Error: ' +
        error.stack +
        '\nReact Component Stack: ' +
        errorInfo.componentStack
    );
  }

  render() {
    if (this.state.hasError) {
      // You can render any custom fallback UI
      return (
        <WeaveMessage>
          Something went wrong. Check the javascript console.
        </WeaveMessage>
      );
    }

    return this.props.children;
  }
}

type MainProps = {
  browserType?: string;
};

const Main = ({browserType}: MainProps) => (
  <React.Suspense fallback="loading">
    <ErrorBoundary>
      <NotebookComputeGraphContextProvider>
        <StateInspector name="WeaveApp">
          <PanelRootContextProvider>
            <WeaveViewerContextProvider>
              <PagePanel browserType={browserType} />
            </WeaveViewerContextProvider>
          </PanelRootContextProvider>
        </StateInspector>
      </NotebookComputeGraphContextProvider>
    </ErrorBoundary>
  </React.Suspense>
);

const basename = getConfig().PREFIX;
ReactDOM.render(
  <ApolloProvider client={apolloClient}>
    <Router basename={basename}>
      <Switch>
        <Route path={`/${URL_BROWSE}/${URL_RECENT}/:assetType?`}>
          <Main browserType={URL_RECENT} />
        </Route>
        <Route path={[`/${URL_BROWSE}/${URL_TEMPLATES}/:templateName?`]}>
          <Main browserType={URL_TEMPLATES} />
        </Route>
        <Route
          path={[
            `/${URL_BROWSE}/${URL_WANDB}/:entity?/:project?/:assetType?/:preview?`,
            `/${URL_BROWSE}/${URL_WANDB}/:entity?/:project?/:assetType?`,
            `/${URL_BROWSE}/${URL_WANDB}/:entity?/:project?`,
            `/${URL_BROWSE}/${URL_WANDB}/:entity?`,
          ]}>
          <Main browserType={URL_WANDB} />
        </Route>
        <Route path={`/${URL_BROWSE}/${URL_LOCAL}/:assetType?/:preview?`}>
          <Main browserType={URL_LOCAL} />
        </Route>
        <Route path="/">
          <Main />
        </Route>
      </Switch>
    </Router>
  </ApolloProvider>,
  document.getElementById('root')
);
