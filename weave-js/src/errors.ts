import {ApolloError} from '@apollo/client';
import {get} from 'lodash';

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
