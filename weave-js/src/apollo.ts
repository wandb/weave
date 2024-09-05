import {
  ApolloClient,
  ApolloLink,
  createHttpLink,
  InMemoryCache,
  Operation,
} from '@apollo/client';
import Observable from 'zen-observable';

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

export const makeGorillaApolloClient = (
  gorillaApolloEndpoint: string = `${window.WEAVE_CONFIG.WANDB_BASE_URL}/graphql`
) => {
  return new ApolloClient({
    link: ApolloLink.from([
      authMiddleware,
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
