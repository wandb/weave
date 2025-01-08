import {TraceServerError} from './wfDataModelHooksInterface';

export function maybeGetReasonFromError(
  error?: Error | TraceServerError
): string | null {
  if (!error) {
    return null;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return error.reason;
}

export function getReasonFromError(
  error?: Error | TraceServerError
): string | null {
  const reason = maybeGetReasonFromError(error);
  if (reason) {
    return reason;
  }
  return JSON.stringify(error);
}

export function maybeGetErrorReasonFromRes(res: any): string | null {
  if ('error' in res) {
    return maybeGetReasonFromError(res.error);
  }
  return maybeGetReasonFromError(res);
}
