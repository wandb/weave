import {datadogRum} from '@datadog/browser-rum';
import * as Sentry from '@sentry/react';
import React, {Component, ErrorInfo, ReactNode} from 'react';

import {weaveErrorToDDPayload} from '../errors';
import {ErrorPanel} from './ErrorPanel';

type Props = {
  children?: ReactNode;
};

type State = {
  hasError: boolean;
};

export class ErrorBoundary extends Component<Props, State> {
  public static getDerivedStateFromError(_: Error): State {
    return {hasError: true};
  }
  public state: State = {
    hasError: false,
  };

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    datadogRum.addAction(
      'weave_panel_error_boundary',
      weaveErrorToDDPayload(error)
    );

    Sentry.captureException(error, {
      tags: {
        weaveErrorBoundary: 'true',
      },
    });
  }

  public render() {
    if (this.state.hasError) {
      return <ErrorPanel />;
    }

    return this.props.children;
  }
}
