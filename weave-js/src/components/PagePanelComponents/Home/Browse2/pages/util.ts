import _ from 'lodash';
import React from 'react';
import {useLocation, useParams} from 'react-router-dom';

export const dummyImageURL =
  'https://github.com/wandb/weave/blob/7cbb458e83a7121042af6ab6894f999210fafa4d/weave-js/src/components/PagePanelComponents/Home/dd_placeholder.png?raw=true';

export const useQuery = () => {
  const {search} = useLocation();

  return React.useMemo(() => {
    const params = new URLSearchParams(search);
    const entries = Array.from(params.entries());
    const searchDict = _.fromPairs(entries);
    return searchDict;
  }, [search]);
};

export const useEPPrefix = () => {
  const params = useParams<{entity: string; project: string}>();
  const {entity, project} = params;
  if (!entity || !project) {
    throw new Error('useEPPrefix must be called within a project route');
  }
  return (path: string) => `/${entity}/${project}${path}`;
}
