import {parseRef} from '@wandb/weave/react';
import _ from 'lodash';
import React from 'react';
import {useLocation} from 'react-router-dom';

import {SmallRef} from '../../Browse2/SmallRef';

export const useURLSearchParamsDict = () => {
  const {search} = useLocation();

  return React.useMemo(() => {
    const params = new URLSearchParams(search);
    const entries = Array.from(params.entries());
    const searchDict = _.fromPairs(entries);
    return searchDict;
  }, [search]);
};

export const truncateID = (id: string, maxLen: number = 9) => {
  if (id.length < maxLen) {
    return id;
  }
  const startLen = Math.floor((maxLen - 3) / 2);
  const endLen = maxLen - 3 - startLen;
  return `${id.slice(0, startLen)}...${id.slice(-endLen)}`;
};

export const renderCell = (value: any) => {
  if (typeof value === 'string' && value.startsWith('wandb-artifact:///')) {
    return <SmallRef objRef={parseRef(value)} />;
  }
  if (typeof value === 'boolean') {
    return value ? 'True' : 'False';
  }
  return value;
};
