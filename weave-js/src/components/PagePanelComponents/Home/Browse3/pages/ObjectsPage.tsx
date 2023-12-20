import React, {useEffect} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../context';

export const ObjectsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  // TODO: Implement in due time if needed
  const {baseRouter} = useWeaveflowRouteContext();
  const history = useHistory();
  useEffect(() => {
    history.push(baseRouter.projectUrl(props.entity, props.project));
  }, [history, props.entity, props.project, baseRouter]);
  return <></>;
};
