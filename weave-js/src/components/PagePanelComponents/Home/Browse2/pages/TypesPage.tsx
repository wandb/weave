import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const TypesPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>TypesPage Placeholder</h1>
      <div>Just a simple listing of all named Types</div>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the type:{' '}
          <Link to={prefix('/type/type_name')}>/type/type_name</Link>
        </li>
      </ul>
    </div>
  );
};
