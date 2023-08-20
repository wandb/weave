import './globalStyleImports';

import React from 'react';
import ReactDOM from 'react-dom';
import {BrowserRouter as Router, Switch, Route} from 'react-router-dom';

import {onAppError} from './components/automation';
import PagePanel from './components/PagePanel';
import {WeaveMessage} from './components/Panel2/WeaveMessage';
import {NotebookComputeGraphContextProvider} from './contextProviders';
import {URL_LOCAL, URL_RECENT, URL_WANDB} from './urls';

// These get popuated via /__frontend/env.js and are defined in weave_server.py
declare global {
  interface Window { 
    CONFIG: {
      PREFIX: string,
      ANALYITCS_DISABLED: boolean,
      WEAVE_BACKEND_HOST: string,
    }
  }
}

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
        <PagePanel browserType={browserType} />
      </NotebookComputeGraphContextProvider>
    </ErrorBoundary>
  </React.Suspense>
);

ReactDOM.render(
  <Router basename={window.CONFIG.PREFIX}>
    <Switch>
      <Route path={`/${URL_RECENT}/:assetType?`}>
        <Main browserType={URL_RECENT} />
      </Route>
      <Route
        path={[
          `/${URL_WANDB}/:entity?/:project?/:assetType?/:preview?`,
          `/${URL_WANDB}/:entity?/:project?/:assetType?`,
          `/${URL_WANDB}/:entity?/:project?`,
          `/${URL_WANDB}/:entity?`,
        ]}>
        <Main browserType={URL_WANDB} />
      </Route>
      <Route path={`/${URL_LOCAL}/:assetType?/:preview?`}>
        <Main browserType={URL_LOCAL} />
      </Route>
      <Route path="/">
        <Main />
      </Route>
    </Switch>
  </Router>,
  document.getElementById('root')
);
