import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const BoardPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>BoardPage Placeholder</h1>
      <div>This is the page for a single board.</div>
      <div>
        The exact URL structure needs some finalizing. We might have a few
        different urls, for example:
      </div>
      <ul>
        <li>
          <pre>/boards/_new_board_</pre>
        </li>
        <li>
          <pre>/boards/:boardId</pre>
        </li>
        <li>
          <pre>/boards/:boardId/version/:versionId</pre>
        </li>
      </ul>
      <div>Migration Notes:</div>
      <ul>
        <li>
          We should re-use the components from the weave home for viewing a
          board
        </li>
        <li>
          We should re-consider persistence and model it off of the workspace
          where one board has many "versions" (aka aliases)
        </li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Back to all boards. <Link to={prefix('/boards')}>/boards</Link>
        </li>
      </ul>
    </div>
  );
};
