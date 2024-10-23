/**
 * This component is loaded when there is no view specifier in query parameters.
 * It looks up the default view for that table and redirects.
 */
import React, {useEffect} from 'react';
import {useHistory} from 'react-router-dom';

import {Loading} from '../../../../../Loading';
import {
  getDefaultView,
  getDefaultViewId,
  savedViewObjectToQuery,
} from '../SavedViews/savedViewUtil';
import {useBaseObjectInstances} from '../wfReactInterface/objectClassQuery';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';

type CallsPageDefaultViewProps = {
  entity: string;
  project: string;
  table: string;
};

export const CallsPageDefaultView = ({
  entity,
  project,
  table,
}: CallsPageDefaultViewProps) => {
  const history = useHistory();
  const projectId = projectIdFromParts({entity, project});

  const defaultViewId = getDefaultViewId(table);
  const query = useBaseObjectInstances('SavedView', {
    project_id: projectId,
    filter: {
      latest_only: true,
      object_ids: [defaultViewId],
    },
  });

  useEffect(() => {
    const {loading, result} = query;
    if (loading) {
      return;
    }

    const viewObj = result?.[0] ?? getDefaultView(projectId, table);
    const search = savedViewObjectToQuery(viewObj);
    history.replace({search});
  }, [history, projectId, table, query]);

  return <Loading />;
};
