import _ from 'lodash';
import React, {useState} from 'react';

import {TargetBlank} from '../../../../../../common/util/links';
import {Button} from '../../../../../Button';
import {Icon} from '../../../../../Icon';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {PanelView} from './PanelView';
import {SavedViewsInfo} from './savedViewUtil';

type PanelSwitchViewProps = {
  savedViewsInfo: SavedViewsInfo;

  onLoadView: (view: TraceObjSchema) => void;
};

export const PanelSwitchView = ({
  savedViewsInfo,
  onLoadView,
}: PanelSwitchViewProps) => {
  const [isShowingInfo, setIsShowingInfo] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const onInfoClick = () => setIsShowingInfo(!isShowingInfo);

  const {views} = savedViewsInfo;
  // Filter views based on search term
  const filteredViews = views.filter(view => 
    view.val.label?.toLowerCase().includes(searchTerm.toLowerCase()) ?? false
  );
  // Sort filtered views by creation date
  // TODO: should we sort currentViewId to top? That wouldn't match Workspaces
  // but seems potentially useful to me.
  const sortedViews = _.orderBy(filteredViews, 'created_at', 'desc');

  return (
    <div className="w-[400px]">
      <div className="relative">
        <Icon
          name="search"
          className="absolute left-16 top-[10px] text-moon-400"
          size="sm"
        />
        <input
          type="text"
          placeholder="Search saved views..."
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          className="w-full pl-[44px] pr-16 pt-8 pb-12 border-b border-moon-200 focus:outline-none"
        />
      </div>
      <div className="flex items-center rounded-[4px] px-16 py-8">
        <div className="font-semibold">Saved views</div>
        <div className="ml-8 bg-oblivion/[0.05] px-6">{views.length}</div>
        <div className="flex-auto"></div>
        <Button
          variant="ghost"
          size="small"
          icon="info"
          onClick={onInfoClick}
          tooltip="Toggle help information"
        />
      </div>
      {isShowingInfo && (
        <div className="rounded-8 mx-16 mb-8 bg-moon-100 px-12 py-8 text-sm text-moon-500">
          Save your custom column configurations, filters, and sorts as Views
          for quick access to your preferred data setups.{' '}
          <TargetBlank href="http://wandb.me/weave_saved_views">
            Learn more about saved views
          </TargetBlank>{' '}
          in Docs.
        </div>
      )}
      <div className="max-h-[calc(100vh-24rem)] overflow-auto">
        {sortedViews.map(view => (
          <PanelView
            key={view.object_id}
            view={view}
            onLoadView={onLoadView}
            isChecked={view.object_id === savedViewsInfo.currentViewId}
            currentViewerId={savedViewsInfo.currentViewerId}
          />
        ))}
      </div>
    </div>
  );
};
