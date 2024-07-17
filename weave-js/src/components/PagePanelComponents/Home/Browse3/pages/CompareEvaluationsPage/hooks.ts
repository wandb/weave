import {useCallback} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';

export const usePeekCall = (entity: string, project: string) => {
  const history = useHistory();
  const {peekingRouter} = useWeaveflowRouteContext();

  return useCallback(
    (callId: string) => {
      const to = peekingRouter.callUIUrl(entity, project, '', callId);
      history.push(to);
    },
    [history, peekingRouter, entity, project]
  );
};
