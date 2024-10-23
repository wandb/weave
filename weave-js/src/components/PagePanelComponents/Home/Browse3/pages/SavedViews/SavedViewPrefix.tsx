import React from 'react';

import {DropdownSwitchView} from './DropdownSwitchView';
import {SavedViewsInfo} from './savedViewUtil';

type SavedViewPrefixProps = {
  savedViewsInfo: SavedViewsInfo;
};

export const SavedViewPrefix = ({savedViewsInfo}: SavedViewPrefixProps) => {
  return (
    <div className="ml-[-8px]">
      <DropdownSwitchView savedViewsInfo={savedViewsInfo} />
    </div>
  );
};
