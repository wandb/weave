import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const ObjectsPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>ObjectsPage Placeholder</h1>
      <div>Just a simple listing of all named Objects</div>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the object:{' '}
          <Link to={prefix('/object/object_name')}>/object/object_name</Link>
        </li>
      </ul>
    </div>
  );
};
