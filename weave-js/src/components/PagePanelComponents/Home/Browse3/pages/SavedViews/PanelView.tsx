/**
 * UI panel for one view that can be loaded.
 */
import React from 'react';

import {IconCheckmark} from '../../../../../Icon';
import {UserName} from '../../../../../UserName';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';

type PanelViewProps = {
  view: TraceObjSchema;
  onLoadView: (view: TraceObjSchema) => void;
  isChecked: boolean;
  currentViewerId: string | null;
};

export const PanelView = ({
  view,
  onLoadView,
  isChecked,
  currentViewerId,
}: PanelViewProps) => {
  const {wb_user_id, val} = view;
  const creatorUserId = wb_user_id ?? null;
  const {label} = val;
  const resolvedName = label ?? 'Untitled view';

  const saveTime = view.created_at
    ? new Date(view.created_at)
        .toLocaleString('en-US', {
          month: 'numeric',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
          hour12: true,
        })
        .toLowerCase()
        .replace(', ', ' at ')
    : null;

  const onClick = () => onLoadView(view);

  let by = null;
  if (!creatorUserId) {
    // creatorUserId will be the empty string for our synthetic default view
  } else if (creatorUserId === currentViewerId) {
    by = 'by you';
  } else {
    by = <UserName prefix="by " userId={creatorUserId} field="username" />;
  }

  return (
    <div
      className="flex w-full cursor-pointer gap-10 px-16 py-8 hover:bg-moon-100"
      onClick={onClick}>
      <div className="flex-auto">
        <div>{resolvedName}</div>
        <div className="text-sm text-moon-500">
          {saveTime && <>Saved on {saveTime} </>}
          {by}
        </div>
      </div>
      <div className="w-[30px] flex-none">{isChecked && <IconCheckmark />}</div>
    </div>
  );
};
