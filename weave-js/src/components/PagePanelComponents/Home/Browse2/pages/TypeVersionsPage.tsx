import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix, useQuery} from './util';

export const TypeVersionsPage: React.FC = () => {
  const search = useQuery();
  const filter = search.filter;
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>TypeVersionsPage Placeholder</h1>
      <h2>Filter: {filter}</h2>
      <div>
        This is the listing page for TypeVersions. A TypeVersion is a "version"
        of a weave "type". In the user's mind it is analogous to a specific
        implementation of a python class.
      </div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          From a content perspective, this is similar to the `versions` table
          available in weaveflow (
          <a href="https://weave.wandb.ai/browse2/dannygoldstein/hooman-eval-notion2/Dataset/eval_dataset">
            example
          </a>
          ) except that rather than just showing the versions of a single type,
          we show all versions of all types, filtered to whatever the user (or
          link source) specified.
        </li>
        <li>
          Notice that the sidebar `Types` links here. This might seem like a
          mistake, but it is not. What the user most likely _wants_ to see is a
          listing of all the _latest_ versions of each type (which is why the
          link filters to latest).
        </li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the associated type version:{' '}
          <Link to={prefix('/types/type_name/versions/version_id')}>
            /types/[type_name]/versions/[version_id]
          </Link>
        </li>
      </ul>
      <div>Inspiration</div>
      This page will basically be a simple table of Type Versions, with some
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
