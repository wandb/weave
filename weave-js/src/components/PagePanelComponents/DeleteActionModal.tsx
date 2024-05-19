import React from 'react';
import {Modal} from 'semantic-ui-react';

import {Button} from '../Button';
import * as M from './Modal.styles';

type DeleteActionModalProps = {
  open: boolean;
  acting: boolean;
  onClose: () => void;
  onDelete: () => void;
  deleteTypeString?: string;
};

export const DeleteActionModal = ({
  open,
  acting,
  onClose,
  onDelete,
  deleteTypeString = 'board',
}: DeleteActionModalProps) => {
  return (
    <Modal
      open={open}
      onClose={onClose}
      closeOnDimmerClick={false}
      size="small">
      <Modal.Content>
        <M.Title>
          Are you sure you want to delete this {deleteTypeString}?
        </M.Title>
        <M.Description>
          Warning - this is a permanent action - it will break any links
          referencing this {deleteTypeString}.
        </M.Description>
        <M.Buttons>
          <Button
            variant="destructive"
            size="large"
            disabled={acting}
            onClick={onDelete}>
            {`Delete ${deleteTypeString}`}
          </Button>
          <Button variant="ghost" size="large" onClick={onClose}>
            Cancel
          </Button>
        </M.Buttons>
      </Modal.Content>
    </Modal>
  );
};
