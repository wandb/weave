import {gql} from '../../../generated/gql';

export const GET_REPORT = gql(`
  query GetReport($id: ID!) {
    view(id: $id) {
      id
      displayName
      spec
    }
  }
`);
