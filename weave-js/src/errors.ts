import {ApolloError} from '@apollo/client';
import {get} from 'lodash';

import {WeaveApp} from './weave';

export class UseNodeValueServerExecutionError extends Error {}

export function extractErrorMessageFromApolloError(
  err: unknown
): string | undefined {
  if (!(err instanceof ApolloError) && !(err instanceof Error)) {
    return;
  }
  const errMsg =
    get(err, 'graphQLErrors[0].message') ??
    get(err, 'networkError.result.errors[0].message') ??
    get(err, 'message');
  return errMsg;
}

export function extractStatusCodeFromApolloError(err: any): number | undefined {
  const statusCode =
    err?.networkError?.statusCode ?? err?.graphQLErrors?.[0]?.statusCode;
  return statusCode;
}

type DDErrorPayload = {
  errorMessage?: string;
  errorName?: string;
  errorStack?: string;
  hashedErrorMessage?: number;
  hashedErrorStack?: number;
  windowLocationURL?: string;
  weaveContext?: any;
  isServerError?: boolean;
};

export const weaveErrorToDDPayload = (
  error: Error,
  weave?: WeaveApp
): DDErrorPayload => {
  try {
    return {
      errorMessage: trimString(error.message),
      errorName: trimString(error.name),
      errorStack: trimString(error.stack),
      hashedErrorMessage: hashStr(error.message),
      hashedErrorStack: hashStr(error.stack),
      windowLocationURL: trimString(window.location.href),
      weaveContext: weave?.client.debugMeta(),
      isServerError: error instanceof UseNodeValueServerExecutionError,
    };
  } catch (e) {
    // If we fail to serialize the error, just return an empty object.
    console.error('Failed to serialize error', e);
    return {};
  }
};

const MAX_CONFIG_STRING_LENGTH = 2500;
export const trimString = (str?: string) => {
  if (str == null) {
    return '';
  }
  if (str.length > MAX_CONFIG_STRING_LENGTH) {
    return str.slice(0, MAX_CONFIG_STRING_LENGTH);
  }
  return str;
};

export const hashStr = (str?: string) => {
  // From https://stackoverflow.com/a/7616484
  let hash = 0;
  let i: number;
  let chr: number;
  if (str == null || str.length === 0) {
    return hash;
  }
  for (i = 0; i < str.length; i++) {
    chr = str.charCodeAt(i);
    // tslint:disable-next-line: no-bitwise
    hash = (hash << 5) - hash + chr;
    // tslint:disable-next-line: no-bitwise
    hash |= 0; // Convert to 32bit integer
  }
  return hash;
};
