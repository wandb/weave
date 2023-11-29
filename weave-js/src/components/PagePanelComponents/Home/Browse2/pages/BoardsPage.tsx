import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const BoardsPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>BoardsPage Placeholder</h1>
      <div>This is the listing page for boards</div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          We should try to reuse as much as possible from the homepage boards
          table view. Most of the query layer should be reusable.
        </li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the associated board:{' '}
          <Link to={prefix('/boards/my_board')}>/boards/my_board</Link>
        </li>
      </ul>
      <div>Inspiration</div>
      <a href="">Link</a>
      <image src="" />
    </div>
  );
};
