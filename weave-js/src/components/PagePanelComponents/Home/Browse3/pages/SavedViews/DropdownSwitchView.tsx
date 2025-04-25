import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import React, {useState} from 'react';

import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {PanelSwitchView} from './PanelSwitchView';
import {SavedViewsInfo} from './savedViewUtil';

type DropdownSwitchViewProps = {
  savedViewsInfo: SavedViewsInfo;
};

export const DropdownSwitchView = ({
  savedViewsInfo,
}: DropdownSwitchViewProps) => {
  const [isOpen, setIsOpen] = useState(false);

  const onLoadView = (view: TraceObjSchema) => {
    setIsOpen(false);
    savedViewsInfo.onLoadView(view);
  };

  return (
    <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenu.Trigger>
        <Button active={isOpen} variant="ghost" icon="menu" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="start">
          <PanelSwitchView
            savedViewsInfo={savedViewsInfo}
            onLoadView={onLoadView}
          />
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
};
