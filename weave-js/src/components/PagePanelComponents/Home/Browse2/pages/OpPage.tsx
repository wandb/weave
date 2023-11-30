import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const OpPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>OpPage Placeholder</h1>
      <div>Just a simple page of the op (named collection of OpVersions).</div>
      <div>Links:</div>
      <ul>
        <li>
          Link to OpVersions for this Op:{' '}
          <Link to={prefix('/op-versions?filter=op=op_name')}>
            /op-versions?filter=op=op_name
          </Link>
        </li>
      </ul>
    </div>
  );
};
