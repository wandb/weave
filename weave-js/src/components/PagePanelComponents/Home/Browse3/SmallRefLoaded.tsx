/**
 * Render a SmallRef after we have all of the necessary data.
 */

import React from 'react';

import {IconName} from '../../../Icon';
import {Link} from './pages/common/Links';
import {SmallRefIcon} from './SmallRefIcon';

type SmallRefLoadedProps = {
  icon: IconName;
  url: string;
  label?: string;
};

export const SmallRefLoaded = ({icon, url, label}: SmallRefLoadedProps) => {
  return (
    <Link $variant="secondary" to={url} className="w-full">
      <div className="flex items-center gap-4">
        <SmallRefIcon icon={icon} />
        {label && (
          <div className="h-[22px] min-w-0 flex-1 overflow-hidden overflow-ellipsis whitespace-nowrap">
            {label}
          </div>
        )}
      </div>
    </Link>
  );
};
