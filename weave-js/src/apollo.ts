import {
  ApolloClient,
  ApolloLink,
  createHttpLink,
  InMemoryCache,
  Operation,
} from '@apollo/client';
import Observable from 'zen-observable';

import {getCookie} from './common/util/cookie';

const makeHttpLink = (uri: string) =>
  createHttpLink({
    fetch: (input: RequestInfo, init?: RequestInit): Promise<Response> => {
      // we force using window.fetch because we need to use datadog's updated instance of window.fetch
      return window.fetch(input, init);
    },
    uri,
    // Our credentials may be a cookie on a different domain to backend
    // `api.wandb.ai` vs `wandb.ai`
    // https://www.apollographql.com/docs/react/networking/authentication/#cookie
    credentials: 'include',
  });

const authMiddleware = new ApolloLink((operation, forward) => {
  return new Observable(observer => {
    setHeader(operation, 'X-Origin', window.location.origin);
    forward(operation).subscribe(observer);
  });
});

const adminPrivilegesMiddleware = new ApolloLink((operation, forward) => {
  const adminPrivileges = getCookie('use_admin_privileges') === 'true';
  if (adminPrivileges) {
    setHeader(operation, 'use-admin-privileges', 'true');
  }
  return forward!(operation);
});
export const makeGorillaApolloClient = (
  gorillaApolloEndpoint: string = `${window.WEAVE_CONFIG.WANDB_BASE_URL}/graphql`
) => {
  return new ApolloClient({
    link: ApolloLink.from([
      authMiddleware,
      adminPrivilegesMiddleware,
      makeHttpLink(gorillaApolloEndpoint),
    ]),
    cache: new InMemoryCache(),
  });
};

interface OperationContext {
  headers?: {[key: string]: string};
}

function setHeader(op: Operation, key: string, value: string) {
  op.setContext(({headers = {}}: OperationContext) => ({
    headers: {
      ...headers,
      [key]: value,
    },
  }));
}
