import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix} from './util';

export const TablesPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>TablesPage Placeholder</h1>
      <div>This is the listing page for tables</div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          We should try to reuse as much as possible from the homepage tables
          table view. Most of the query layer should be reusable.
        </li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the associated table:{' '}
          <Link to={prefix('/tables/my_table')}>/tables/my_table</Link>
        </li>
      </ul>
      <div>Inspiration</div>
      <a href="https://weave.wandb.test/browse/wandb/timssweeney/weave/table">
        Link
      </a>
      <br />
      <img
        src="https://github.com/wandb/weave/blob/db555a82512c2bac881ee0c65cf6d33264f4d34c/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/tables_example.png?raw=true"
        style={{
          width: '100%',
        }}
      />
    </div>
  );
};
