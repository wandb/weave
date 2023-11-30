import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix, useQuery} from './util';

export const TypeVersionPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>TypeVersionPage Placeholder</h1>
      <div>
        This is the detail page for TypeVersion. A TypeVersion is a "version" of
        a weave "type". In the user's mind it is analogous to a specific
        implementation of a python class.
      </div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          Weaveflow pretty much already has this page (
          <a href="https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/Dataset/eval_dataset/696d98783ec24548e08b">
            https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/Dataset/eval_dataset/696d98783ec24548e08b
          </a>
          ) that includes most of what we will want here. However, this is one
          of the most important pages, so it is is worth enumerating the primary
          features
        </li>
      </ul>
      <div>Primary Features:</div>
      <ul>
        <li></li>
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
      Existing Weaveflow Page
      <br />
      <img
        src="https://github.com/wandb/weave/blob/db555a82512c2bac881ee0c65cf6d33264f4d34c/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/simple_table.png?raw=true"
        style={{
          width: '100%',
        }}
      />
    </div>
  );
};
