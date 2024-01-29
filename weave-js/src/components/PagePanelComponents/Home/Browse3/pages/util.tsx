import {Box} from '@material-ui/core';
import {parseRef} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';
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
  if (typeof value === 'number') {
    return (
      <Box
        sx={{
          textAlign: 'right',
          width: '100%',
        }}>
        {value.toFixed(4)}
      </Box>
    );
  }
  return value;
};

export const useInitializingFilter = <T,>(
  initialFilter?: Partial<T>,
  onFilterUpdate?: (filter: T) => void
) => {
  const [filterState, setFilterState] = useState<Partial<T>>(
    initialFilter ?? {}
  );
  useEffect(() => {
    if (initialFilter) {
      setFilterState(initialFilter);
    }
  }, [initialFilter]);

  // If the caller is controlling the filter, use the caller's filter state
  const filter = useMemo(
    () => (onFilterUpdate ? initialFilter ?? ({} as Partial<T>) : filterState),
    [filterState, initialFilter, onFilterUpdate]
  );
  const setFilter = useMemo(
    () => (onFilterUpdate ? onFilterUpdate : setFilterState),
    [onFilterUpdate]
  );

  return {filter, setFilter};
};
