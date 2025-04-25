import React from 'react';

import {useProjectInfo} from '../../../../../../common/hooks/useProjectInfo';
import {useViewerInfo} from '../../../../../../common/hooks/useViewerInfo';
import {Alert} from '../../../../../Alert';
import {Loading} from '../../../../../Loading';
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
    return <Loading />;
  }
  if (!userInfo) {
    return <Alert severity="error">User not found</Alert>;
  }
  if (!projectInfo) {
    return <Alert severity="error">Invalid project: {project}</Alert>;
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
