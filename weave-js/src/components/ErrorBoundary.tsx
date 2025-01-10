import {datadogRum} from '@datadog/browser-rum';
import * as Sentry from '@sentry/react';
import React, {Component, ErrorInfo, ReactNode} from 'react';
import {v4 as uuidv4} from 'uuid';

import {weaveErrorToDDPayload} from '../errors';
import {ErrorPanel} from './ErrorPanel';

type Props = {
  children?: ReactNode;
};

type State = {
  uuid: string | undefined;
  timestamp: Date | undefined;
  error: Error | undefined;
};

export class ErrorBoundary extends Component<Props, State> {
  public static getDerivedStateFromError(error: Error): State {
    return {uuid: uuidv4(), timestamp: new Date(), error};
  }
  public state: State = {
    uuid: undefined,
    timestamp: undefined,
    error: undefined,
  };

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const {uuid} = this.state;
    datadogRum.addAction(
      'weave_panel_error_boundary',
      weaveErrorToDDPayload(error, undefined, uuid)
    );
    Sentry.captureException(error, {
      extra: {
        uuid,
      },
      tags: {
        weaveErrorBoundary: 'true',
      },
    });
  }

  public render() {
    const {uuid, timestamp, error} = this.state;
    if (error != null) {
      return <ErrorPanel uuid={uuid} timestamp={timestamp} error={error} />;
    }

    return this.props.children;
  }
}
