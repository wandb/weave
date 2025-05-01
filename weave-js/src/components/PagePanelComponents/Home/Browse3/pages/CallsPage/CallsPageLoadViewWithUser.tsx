import React from 'react';

import {ProjectInfo} from '../../../../../../common/hooks/useProjectInfo';
import {UserInfo} from '../../../../../../common/hooks/useViewerInfo';
import {Loading} from '../../../../../Loading';
import {useSavedViewInstances} from '../SavedViews/savedViewUtil';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {CallsPageLoaded} from './CallsPageLoaded';

type CallsPageLoadViewWithUserProps = {
  entity: string;
  project: string;
  tab: string;
  view?: string;
  userInfo: UserInfo | null;
  projectInfo: ProjectInfo;
};

export const CallsPageLoadViewWithUser = ({
  entity,
  project,
  tab,
  view,
  userInfo,
  projectInfo,
}: CallsPageLoadViewWithUserProps) => {
  const projectId = projectIdFromParts({entity, project});

  // Traces table might be under 'calls'
  const table = tab === 'evaluations' ? 'evaluations' : 'traces';

  const savedViewInstances = useSavedViewInstances(projectId, table);
  if (savedViewInstances.loading) {
    return <Loading />;
  }
  const {views, refetchViews: fetchViews} = savedViewInstances;

  const defaultView = views[views.length - 1];
  let baseView = null;
  if (view) {
    baseView = views.find(v => v.object_id === view) ?? defaultView;
  } else {
    baseView = defaultView;
  }

  return (
    <CallsPageLoaded
      entity={entity}
      project={project}
      table={table}
      baseView={baseView}
      fetchViews={fetchViews}
      views={views}
      userInfo={userInfo}
      projectInfo={projectInfo}
    />
  );
};
