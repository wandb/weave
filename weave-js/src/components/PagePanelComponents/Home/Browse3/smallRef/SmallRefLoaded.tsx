/**
 * Render a SmallRef after we have all of the necessary data.
 */

import classNames from 'classnames';
import React from 'react';

import {IconName} from '../../../../Icon';
import {Tooltip} from '../../../../Tooltip';
import {Link} from '../pages/common/Links';
import {getErrorReason} from '../pages/wfReactInterface/utilities';
import {SmallRefIcon} from './SmallRefIcon';

type SmallRefLoadedProps = {
  icon: IconName;
  url: string;
  label?: string;
  error: Error | null;
};

export const SmallRefLoaded = ({
  icon,
  url,
  label,
  error,
}: SmallRefLoadedProps) => {
  const content = (
    <div
      className={classNames('flex items-center gap-4 text-moon-700', {
        'hover:text-teal-500': !error,
        'line-through': error,
      })}>
      <SmallRefIcon icon={icon} />
      {label && (
        <div className="h-[22px] min-w-0 flex-1 overflow-hidden overflow-ellipsis whitespace-nowrap">
          {label}
        </div>
      )}
    </div>
  );
  if (error) {
    const reason = getErrorReason(error);
    return (
      <Tooltip
        trigger={<div className="w-full">{content}</div>}
        noTriggerWrap
        content={reason}
      />
    );
  }
  return (
    <Link $variant="secondary" to={url} className="w-full">
      {content}
    </Link>
  );
};
