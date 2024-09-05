import {
  ApolloClient,
  ApolloLink,
  createHttpLink,
  InMemoryCache,
  Operation,
} from '@apollo/client';
import Observable from 'zen-observable';

const httpLink = createHttpLink({
  fetch: (input: RequestInfo, init?: RequestInit): Promise<Response> => {
    // we force using window.fetch because we need to use datadog's updated instance of window.fetch
    return window.fetch(input, init);
  },
  uri: `${window.WEAVE_CONFIG.WANDB_BASE_URL}/graphql`,
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

// This is a hard-coded client that is used in the old weave.wandb.ai and should
// be removed with that codebase. Using this is INVALID in any proper wandb app.
export const deprecatedApolloClientDoNotUse = new ApolloClient({
  link: ApolloLink.from([authMiddleware, httpLink]),
  cache: new InMemoryCache(),
});

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
