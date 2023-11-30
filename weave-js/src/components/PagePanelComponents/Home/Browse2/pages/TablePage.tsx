import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const TablePage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>TablePage Placeholder</h1>
      <div>This is fullpage view for a table</div>
      <div>Migration Notes:</div>
      <ul>
        <li>Very similar to the preview view in current weave home</li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Open in Board
          <Link to={prefix('/boards/_new_board_')}>/boards/_new_board_</Link>
        </li>
        <li>
          Back to all tables. <Link to={prefix('/tables')}>/tables</Link>
        </li>
      </ul>
      <div>Inspiration</div>
      This page will basically be a simple table of Op Versions, with some
      lightweight filtering on top.
      <br />
      <img
        src="https://github.com/wandb/weave/blob/0fe070497bbde538475efad27cbf147823bc959b/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/table_example.png?raw=true"
        style={{
          width: '100%',
        }}
      />
    </div>
  );
};
