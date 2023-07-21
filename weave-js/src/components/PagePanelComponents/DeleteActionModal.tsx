import {Modal} from 'semantic-ui-react';
import React from 'react';
import {WBButton} from '@wandb/weave/common/components/elements/WBButtonNew';
import * as M from './Modal.styles';

type DeleteActionModalProps = {
  open: boolean;
  acting: boolean;
  onClose: () => void;
  onDelete: () => void;
};

export const DeleteActionModal = ({
  open,
  acting,
  onClose,
  onDelete,
}: DeleteActionModalProps) => {
  return (
    <Modal
      open={open}
      onClose={onClose}
      closeOnDimmerClick={false}
      size="small">
      <Modal.Content>
        <M.Title>Are you sure you want to delete this board?</M.Title>
        <M.Description>
          Warning - this is a permanent action - it will break any links
          referencing this board.
        </M.Description>
        <M.Buttons>
          <WBButton variant="confirm" disabled={acting} onClick={onDelete}>
            Delete board
          </WBButton>
          <WBButton variant="ghost" onClick={onClose}>
            Cancel
          </WBButton>
        </M.Buttons>
      </Modal.Content>
    </Modal>
  );
};
