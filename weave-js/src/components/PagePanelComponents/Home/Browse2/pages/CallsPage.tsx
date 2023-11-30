import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix, useQuery} from './util';

export const CallsPage: React.FC = () => {
  const search = useQuery();
  const filter = search.filter;
  const prefix = useEPPrefix();
  return (
    <div>
      <h1>CallsPage Placeholder</h1>
      <h2>Filter: {filter}</h2>
      <div>
        This is <strong>A VERY IMPORTANT PAGE</strong>. This is a rich, realtime
        datagrid of calls. The best product analogy here is datadog's traces
        page (see below). It is critical that linkers and users can filter this
        page to see exactly what they want. Moreover, it is critical that the
        user can view in a board. The user should also be able to do more
        advanced things like pivot, unnest, etc... in order to create comparison
        or analysis views inline. Plots should be automatically generated above
        the tables.
      </div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          Weaveflow has an existing concept of a run table that shows up on the
          opversion page. This can have builtin filters from the linker. For
          example, see here:{' '}
          <a href="https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/OpDef/EvaluateLLM-compute/40de89370d4563806d5c?inputUri=wandb-artifact%3A%2F%2F%2Fdannygoldstein%2Fhooman-eval-notion2%2Feval_dataset%3A696d98783ec24548e08b%2Fobj">
            https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/OpDef/EvaluateLLM-compute/40de89370d4563806d5c?inputUri=wandb-artifact%3A%2F%2F%2Fdannygoldstein%2Fhooman-eval-notion2%2Feval_dataset%3A696d98783ec24548e08b%2Fobj
          </a>
          <img
            style={{
              width: '75%',
            }}
            src="https://github.com/wandb/weave/blob/4bd192e7a8936d7bd16a5ecd70675804674215e0/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/wf_filtered_calls_example.png?raw=true"
          />
        </li>
        <li>
          Notice that the sidebar links (Traces and the user-terms like
          'evaluate') link here, each with predefined filters. Trace links here
          with `parent_id=null` in order to only show trace roots. While The
          others link with `kind=evaluate` for example. We still need to
          implement a grouping of ops so that we can properly do this "kind"
          lookup. In the beginning, it will be fairly heuristic based until this
          is implemented
        </li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the associated call:{' '}
          <Link to={prefix('/calls/call_id')}>/calls/[call_id]</Link>. Note:
          This might prefer to be a slideout like Notion rather than a full link
          to allow for "peeking".
        </li>
      </ul>
      <div>Inspiration</div>
      <img
        src="https://github.com/wandb/weave/blob/7cbb458e83a7121042af6ab6894f999210fafa4d/weave-js/src/components/PagePanelComponents/Home/dd_placeholder.png?raw=true"
        style={{
          width: '100%',
        }}
      />
    </div>
  );
};
