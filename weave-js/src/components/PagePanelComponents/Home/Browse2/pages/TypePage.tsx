import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const TypePage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>TypePage Placeholder</h1>
      <div>
        Just a simple page of the Type (named collection of TypeVersions).
      </div>
      <div>Links:</div>
      <ul>
        <li>
          Link to TypeVersions for this Type:{' '}
          <Link to={prefix('/type-versions?filter=type=type_name')}>
            /type-versions?filter=type=type_name
          </Link>
        </li>
        <li>
          Link to TypeVersions for this Type (possibly consider including any
          subtypes):{' '}
          <Link to={prefix('/type-versions?filter=sub_type=type_name')}>
            /type-versions?filter=sub_type=type_name
          </Link>
        </li>
      </ul>
    </div>
  );
};
