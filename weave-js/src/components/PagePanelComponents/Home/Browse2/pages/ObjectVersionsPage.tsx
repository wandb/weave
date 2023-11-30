import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix, useQuery} from './util';

export const ObjectVersionsPage: React.FC = () => {
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>ObjectVersionsPage Placeholder</h1>
      <div>
        This is <strong>A VERY IMPORTANT PAGE</strong>. This is a rich, realtime
        datagrid of all ObjectVersions. It is critical that linkers and users
        can filter this page to see exactly what they want. Moreover, it is
        critical that the user can view in a board. The user should also be able
        to do more advanced things like pivot, unnest, etc... in order to create
        comparison or analysis views inline. Plots should be automatically
        generated above the tables. The featureset is very similar to the
        CallsPage, but operating on ObjectVersions.
      </div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          THIS IS COMPLETELY MISSING IN WEAVEFLOW. There is a VersionsTable, but
          it is nearly empty and not filterable/dynamic and scoped to a single
          object.
        </li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the associated ObjectVersion:{' '}
          <Link to={prefix('/objects/object_name/versions/version_id')}>
            /objects/object_name/versions/version_id
          </Link>
          . Note: This might prefer to be a slideout like Notion rather than a
          full link to allow for "peeking".
        </li>
      </ul>
      <div>Inspiration</div>
      The Datadog Traces page is a great point of inspiration for this page.
      <br />
      <img
        src="https://github.com/wandb/weave/blob/7cbb458e83a7121042af6ab6894f999210fafa4d/weave-js/src/components/PagePanelComponents/Home/dd_placeholder.png?raw=true"
        style={{
          width: '100%',
        }}
      />
    </div>
  );
};

// https://github.com/wandb/weave/blob/7cbb458e83a7121042af6ab6894f999210fafa4d/weave-js/src/components/PagePanelComponents/Home/dd_placeholder.png?raw=true
