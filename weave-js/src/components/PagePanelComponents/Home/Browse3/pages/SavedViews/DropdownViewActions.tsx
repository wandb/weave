import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useState} from 'react';

import {SavedViewsInfo} from './savedViewUtil';

type DropdownViewActionsProps = {
  savedViewsInfo: SavedViewsInfo;
};

export const DropdownViewActions = ({
  savedViewsInfo,
}: DropdownViewActionsProps) => {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenu.Trigger>
        <Button active={isOpen} variant="quiet" icon="overflow-horizontal" />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="start">
          <DropdownMenu.Item onClick={savedViewsInfo.onSaveNewView}>
            <Icon name="add-new" /> Save as new view
          </DropdownMenu.Item>
          {/* Implement after object deletion exists */}
          {/* <DropdownMenu.Separator />
          <DropdownMenu.Item>
            <Icon name="delete" /> Delete view
          </DropdownMenu.Item> */}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
};
