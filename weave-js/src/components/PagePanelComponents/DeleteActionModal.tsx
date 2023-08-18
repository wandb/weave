import {Modal} from 'semantic-ui-react';
import React from 'react';
import * as M from './Modal.styles';
import {Button} from '../Button';

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
        <M.Title>{`Are you sure you want to delete this ${deleteTypeString}?`}</M.Title>
        <M.Description>
          {`Warning - this is a permanent action - it will break any links
          referencing this ${deleteTypeString}.`}
        </M.Description>
        <M.Buttons>
          <Button disabled={acting} onClick={onDelete}>
            {`Delete ${deleteTypeString}`}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </M.Buttons>
      </Modal.Content>
    </Modal>
  );
};
