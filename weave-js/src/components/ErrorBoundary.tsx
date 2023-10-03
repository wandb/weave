import React, {Component, ErrorInfo, ReactNode} from 'react';
import {ErrorPanel} from './ErrorPanel';
import {datadogRum} from '@datadog/browser-rum';
import {errorToPayload} from '../errors';

type Props = {
  children?: ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(_: Error): State {
    return {hasError: true};
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // TODO: Log to error reporting service?
    datadogRum.addAction('weave_panel_error_boundary', errorToPayload(error));
  }

  public render() {
    if (this.state.hasError) {
      return <ErrorPanel />;
    }

    return this.props.children;
  }
}
