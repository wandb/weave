import React, {useEffect} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../context';

export const TypesPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  // TODO: Implement in due time if needed
  const routerContext = useWeaveflowRouteContext();
  const history = useHistory();
  useEffect(() => {
    history.push(routerContext.projectUrl(props.entity, props.project));
  }, [history, props.entity, props.project, routerContext]);
  return <></>;
};
