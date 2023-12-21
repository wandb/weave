import React, {useEffect} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowPeekAwareRouteContext} from '../context';

export const ObjectsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  // TODO: Implement in due time if needed
  const routerContext = useWeaveflowPeekAwareRouteContext();
  const history = useHistory();
  useEffect(() => {
    history.push(routerContext.projectUrl(props.entity, props.project));
  }, [history, props.entity, props.project, routerContext]);
  return <></>;
};
