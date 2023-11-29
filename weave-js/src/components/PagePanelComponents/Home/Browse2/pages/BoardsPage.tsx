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
      <a href="https://weave.wandb.test/browse/wandb/timssweeney/weave/board">
        Link
      </a>
      <br />
      <img
        src="https://github.com/wandb/weave/blob/562a679a24ede63dcf4295476a52d7dc38d4bd04/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/boards_example.png?raw=true"
        style={{
          width: '100%',
          maxWidth: '800px',
        }}
      />
    </div>
  );
};
