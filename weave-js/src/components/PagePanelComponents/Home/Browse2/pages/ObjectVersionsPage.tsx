import {Typography} from '@mui/material';
import _ from 'lodash';
import React, {FC} from 'react';

import {dummyImageURL, useQuery} from './util';

export const ObjectVersionsPage: FC = props => {
  const search = useQuery();
  const filter = search.filter;
  return (
    <>
      <Typography variant="h3" component="h3" gutterBottom>
        Objects {filter}
      </Typography>
      <div
        style={{
          backgroundImage: `url(${dummyImageURL})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          width: '100%',
          height: '100%',
        }}
      />
    </>
  );
};
