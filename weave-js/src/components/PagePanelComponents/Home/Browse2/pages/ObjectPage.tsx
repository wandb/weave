import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const ObjectPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>ObjectPage Placeholder</h1>
      <div>
        Just a simple page of the Object (named collection of ObjectVersions).
      </div>
      <div>Links:</div>
      <ul>
        <li>
          Link to ObjectVersions for this Object:{' '}
          <Link to={prefix('/object-versions?filter=object=object_name')}>
            /object-versions?filter=object=object_name
          </Link>
        </li>
      </ul>
    </div>
  );
};
