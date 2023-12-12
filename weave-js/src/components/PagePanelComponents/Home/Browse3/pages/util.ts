import _ from 'lodash';
import React from 'react';
import {useLocation} from 'react-router-dom';

export const useURLSearchParamsDict = () => {
  const {search} = useLocation();

  return React.useMemo(() => {
    const params = new URLSearchParams(search);
    const entries = Array.from(params.entries());
    const searchDict = _.fromPairs(entries);
    return searchDict;
  }, [search]);
};
