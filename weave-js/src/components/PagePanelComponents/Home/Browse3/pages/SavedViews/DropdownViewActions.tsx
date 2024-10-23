import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useState} from 'react';

import {ConfirmDeleteDialog} from './ConfirmDeleteDialog';
import {SavedViewsInfo} from './savedViewUtil';

type DropdownViewActionsProps = {
  savedViewsInfo: SavedViewsInfo;
};

export const DropdownViewActions = ({
  savedViewsInfo,
}: DropdownViewActionsProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const onClickDelete = () => {
    setConfirmDelete(true);
  };

  return (
    <>
      <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
        <DropdownMenu.Trigger>
          <Button active={isOpen} variant="ghost" icon="overflow-horizontal" />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="end">
            <DropdownMenu.Item onClick={savedViewsInfo.onSaveNewView}>
              <Icon name="add-new" /> Save as new view
            </DropdownMenu.Item>
            <DropdownMenu.Separator />
            <DropdownMenu.Item
              disabled={savedViewsInfo.isDefault}
              onClick={onClickDelete}>
              <Icon name="delete" /> Delete view
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      {confirmDelete && (
        <ConfirmDeleteDialog
          setConfirmDelete={setConfirmDelete}
          onDeleteCallback={savedViewsInfo.onDeleteView}
        />
      )}
    </>
  );
};
