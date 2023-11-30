import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const OpsPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>OpsPage Placeholder</h1>
      <div>Just a simple listing of all named Ops</div>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the op:{' '}
          <Link to={prefix('/op/op_name')}>/op/op_name</Link>
        </li>
      </ul>
    </div>
  );
};
