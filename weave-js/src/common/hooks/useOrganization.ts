import {gql} from '@apollo/client';
import {useEffect, useState} from 'react';

import {apolloClient} from '../../apollo';
import {useIsMounted} from './useIsMounted';

export const ORGANIZATION_QUERY = gql`
  query Organization($entityName: String) {
    entity(name: $entityName) {
      id
      organization {
        id
        name
      }
    }
  }
`;

export const useOrgName = ({
  entityName,
  skip,
}: {
  entityName: string;
  skip?: boolean;
}) => {
  const [orgName, setOrgName] = useState<string | null>(null);
  const isMounted = useIsMounted();

  useEffect(
    () => {
      if (skip) {
        return;
      }
      apolloClient
        .query({
          query: ORGANIZATION_QUERY as any,
          variables: {
            entityName,
          },
        })
        .then(result => {
          const info = result?.data?.entity?.organization?.name || entityName;
          if (isMounted()) {
            setOrgName(info);
          }
          return info;
        });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [skip]
  );
  if (!orgName) {
    return {loading: true, orgName: ''};
  }
  return {loading: false, orgName};
};
