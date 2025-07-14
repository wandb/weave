import {FC, useCallback, useContext, useMemo} from 'react';
import React from 'react';
import {Link} from 'react-router-dom';

import {
  useEntityProject,
  useWeaveflowRouteContext,
  WeaveflowPeekContext,
} from '../../context';

export interface TurnAnchorProps {
  turnId: string;
}

export const TurnAnchor: FC<TurnAnchorProps> = ({turnId}) => {
  const {peekingRouter, baseRouter} = useWeaveflowRouteContext();
  const {entity, project} = useEntityProject();
  const {setPreviousUrl, isPeeking} = useContext(WeaveflowPeekContext);

  const to = useMemo(() => {
    // If we're already in a peek view, use peekingRouter to open another peek
    // If we're not in a peek view, use baseRouter for normal navigation
    const router = isPeeking ? peekingRouter : baseRouter;
    return router.callUIUrl(entity, project, '', turnId, turnId, false, false);
  }, [entity, project, turnId, peekingRouter, baseRouter, isPeeking]);

  const handleClick = useCallback(() => {
    if (setPreviousUrl && isPeeking) {
      // Only store previousUrl if we're in a peek view
      const currentUrl = window.location.pathname + window.location.search;
      setPreviousUrl(currentUrl);
    }
  }, [setPreviousUrl, isPeeking]);

  return (
    <div
      className={
        'flex justify-between rounded-lg bg-blue-300 py-12 pl-12 pr-16 text-blue-650'
      }>
      <span>
        <span className={'font-semibold'}>
          No chat view available for this turn.
        </span>{' '}
        You can inspect inputs and outputs in the trace view
      </span>
      <Link
        to={to}
        onClick={handleClick}
        className="font-semibold hover:text-blue-500">
        View trace
      </Link>
    </div>
  );
};
