import './globalStyleImports';

import React from 'react';
import ReactDOM from 'react-dom';

import {onAppError} from './components/automation';
import PagePanel from './components/PagePanel';
import {WeaveMessage} from './components/Panel2/WeaveMessage';
import {NotebookComputeGraphContextProvider} from './contextProviders';

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

ReactDOM.render(
  <React.Suspense fallback={'loading'}>
    <ErrorBoundary>
      <NotebookComputeGraphContextProvider>
        <PagePanel />
      </NotebookComputeGraphContextProvider>
    </ErrorBoundary>
  </React.Suspense>,
  document.getElementById('root')
);
