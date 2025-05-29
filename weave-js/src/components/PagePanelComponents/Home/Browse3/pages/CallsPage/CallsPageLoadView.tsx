import React from 'react';

import {useProjectInfo} from '../../../../../../common/hooks/useProjectInfo';
import {useViewerInfo} from '../../../../../../common/hooks/useViewerInfo';
import {Alert} from '../../../../../Alert';
import {WaveLoader} from '../../../../../Loaders/WaveLoader';
import {CallsPageLoadViewWithUser} from './CallsPageLoadViewWithUser';

type CallsPageLoadViewProps = {
  entity: string;
  project: string;
  tab: string;
  view?: string;
};

export const CallsPageLoadView = ({
  entity,
  project,
  tab,
  view,
}: CallsPageLoadViewProps) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const {loading: loadingProjectInfo, projectInfo} = useProjectInfo(
    entity,
    project
  );

  if (loadingUserInfo || loadingProjectInfo) {
    return (
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100%',
          width: '100%',
          backgroundColor: 'rgba(255, 255, 255, 0.5)',
          zIndex: 1,
        }}>
        <WaveLoader size="huge" />
      </div>
    );
  }
  if (!projectInfo) {
    return <Alert severity="error">Invalid project!!: {project}</Alert>;
  }

  return (
    <CallsPageLoadViewWithUser
      entity={entity}
      project={project}
      tab={tab}
      view={view}
      userInfo={userInfo}
      projectInfo={projectInfo}
    />
  );
};
