import React from 'react';

import {useProjectInfo} from '../../../../../../common/hooks/useProjectInfo';
import {useViewerInfo} from '../../../../../../common/hooks/useViewerInfo';
import {Alert} from '../../../../../Alert';
import {WaveLoader} from '../../../../../Loaders/WaveLoader';
import {useEntityProject} from '../../context';
import {useSavedViewInstances} from '../SavedViews/savedViewUtil';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {ThreadsPageSavedViewControl} from './ThreadsPageSavedViewControl';

type ThreadsPageLoadViewProps = {
  view?: string;
};

export const ThreadsPageLoadView = ({view}: ThreadsPageLoadViewProps) => {
  const {entity, project} = useEntityProject();
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const {loading: loadingProjectInfo, projectInfo} = useProjectInfo(
    entity,
    project
  );

  const projectId = projectIdFromParts({entity, project});
  const savedViewInstances = useSavedViewInstances(projectId, 'threads');

  if (loadingUserInfo || loadingProjectInfo || savedViewInstances.loading) {
    return (
      <div className="fixed inset-0 z-10 flex items-center justify-center bg-white/50">
        <WaveLoader size="huge" />
      </div>
    );
  }
  if (!projectInfo) {
    return <Alert severity="error">Invalid project: {project}</Alert>;
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
    <ThreadsPageSavedViewControl
      baseView={baseView}
      fetchViews={fetchViews}
      views={views}
      userInfo={userInfo}
      projectInfo={projectInfo}
    />
  );
};
