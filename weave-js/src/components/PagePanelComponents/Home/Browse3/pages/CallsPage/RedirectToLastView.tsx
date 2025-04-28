import React from 'react';
import {Redirect, useLocation} from 'react-router-dom';

import {useProjectInfo} from '../../../../../../common/hooks/useProjectInfo';
import {safeLocalStorage} from '../../../../../../core/util/localStorage';
import {Alert} from '../../../../../Alert';
import {Loading} from '../../../../../Loading';
import {getDefaultViewId} from '../SavedViews/savedViewUtil';

type RedirectToLastViewProps = {
  entity: string;
  project: string;
  tab: string;
};

export const RedirectToLastView = ({
  entity,
  project,
  tab,
}: RedirectToLastViewProps) => {
  const location = useLocation();
  const {loading: loadingProjectInfo, projectInfo} = useProjectInfo(
    entity,
    project
  );
  if (loadingProjectInfo) {
    return <Loading />;
  }
  if (!projectInfo) {
    return <Alert severity="error">Invalid project: {project}</Alert>;
  }

  // Traces table might be under 'calls'
  const viewType = tab === 'evaluations' ? 'evaluations' : 'traces';
  const localStorageKey = `SavedView.lastViewed.${projectInfo.internalIdEncoded}.${viewType}`;
  const defaultView = getDefaultViewId(viewType);
  const lastView = safeLocalStorage.getItem(localStorageKey) ?? defaultView;

  // Create a new URLSearchParams object from the current query parameters
  const searchParams = new URLSearchParams();
  searchParams.set('view', lastView);

  // Return the Redirect component to navigate to the updated URL
  return <Redirect to={`${location.pathname}?${searchParams.toString()}`} />;
};
