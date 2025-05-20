import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {Icon} from '@wandb/weave/components/Icon';
import copyToClipboard from 'copy-to-clipboard';
import React, {useCallback, useState} from 'react';
import {toast} from 'react-toastify';

import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {ConfirmDeleteDialog} from './ConfirmDeleteDialog';
import {SavedViewsInfo} from './savedViewUtil';

// TODO: We may want to refine this feature and expose to users.
const ENABLE_DEBUG_ACTIONS = false;

type DropdownViewActionsProps = {
  savedViewsInfo: SavedViewsInfo;
};

const getObjSchemaUrl = (objSchema: TraceObjSchema) => {
  return `weave:///${objSchema.project_id}/object/${objSchema.object_id}:${objSchema.digest}`;
};

export const DropdownViewActions = ({
  savedViewsInfo,
}: DropdownViewActionsProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const onCopy = useCallback(() => {
    const url = getObjSchemaUrl(savedViewsInfo.baseView);
    const code = `import weave\nview = weave.SavedView.load('${url}')`;
    copyToClipboard(code);
    toast('Copied to clipboard');
  }, [savedViewsInfo.baseView]);
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
            {ENABLE_DEBUG_ACTIONS && (
              <>
                <DropdownMenu.Separator />
                <DropdownMenu.Item onClick={onCopy}>
                  <Icon name="copy" /> Copy code
                </DropdownMenu.Item>
              </>
            )}
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
