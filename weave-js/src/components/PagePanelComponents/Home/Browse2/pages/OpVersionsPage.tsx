import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix, useQuery} from './util';

export const OpVersionsPage: React.FC = () => {
  const search = useQuery();
  const filter = search.filter;
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>OpVersionsPage Placeholder</h1>
      <h2>Filter: {filter}</h2>
      <div>
        This is the listing page for OpVersions. An OpVersion is a "version" of
        a weave "op". In the user's mind it is analogous to a specific
        implementation of a method.
      </div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          There are a few tables in Weaveflow that are close to this, but none
          that are exactly what we want.
        </li>
        <li>
          Notice that the sidebar `Operations` links here. This might seem like
          a mistake, but it is not. What the user most likely _wants_ to see is
          a listing of all the _latest_ versions of each op (which is why the
          link filters to latest).
        </li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the associated op version:{' '}
          <Link to={prefix('/ops/op_name/versions/version_id')}>
            /ops/[op_name]/versions/[version_id]
          </Link>
        </li>
      </ul>
      <div>Inspiration</div>
      This page will basically be a simple table of Op Versions, with some
      lightweight filtering on top.
      <br />
      <img
        src="https://github.com/wandb/weave/blob/db555a82512c2bac881ee0c65cf6d33264f4d34c/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/simple_table.png?raw=true"
        style={{
          width: '100%',
        }}
        alt=""
      />
    </div>
  );
};
