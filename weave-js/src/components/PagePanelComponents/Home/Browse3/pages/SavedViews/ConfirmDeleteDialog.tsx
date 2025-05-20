import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import React, {useState} from 'react';
import styled from 'styled-components';

// TODO: Need to cleanup duplication with CallPage OverflowMenu
const DialogContent = styled(MaterialDialogContent)`
  padding: 0 32px !important;
`;
DialogContent.displayName = 'S.DialogContent';

const DialogTitle = styled(MaterialDialogTitle)`
  padding: 32px 32px 16px 32px !important;

  h2 {
    font-weight: 600;
    font-size: 24px;
    line-height: 30px;
  }
`;
DialogTitle.displayName = 'S.DialogTitle';

const DialogActions = styled(MaterialDialogActions)<{$align: string}>`
  justify-content: ${({$align}) =>
    $align === 'left' ? 'flex-start' : 'flex-end'} !important;
  padding: 32px 32px 32px 32px !important;
`;
DialogActions.displayName = 'S.DialogActions';

type ConfirmDeleteDialogProps = {
  setConfirmDelete: (confirmDelete: boolean) => void;
  onDeleteCallback: () => void;
};

export const ConfirmDeleteDialog = ({
  setConfirmDelete,
  onDeleteCallback,
}: ConfirmDeleteDialogProps) => {
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDelete = () => {
    setDeleteLoading(true);
    onDeleteCallback();
    setDeleteLoading(false);
    setConfirmDelete(false);
  };
  return (
    <Dialog
      open={true}
      onClose={() => {
        setConfirmDelete(false);
        setError(null);
      }}
      maxWidth="xs"
      fullWidth>
      <DialogTitle>Delete this view?</DialogTitle>
      <DialogContent style={{overflow: 'hidden'}}>
        {error != null ? (
          <p style={{color: 'red'}}>{error}</p>
        ) : (
          <p>
            You can delete this view if you believe it is no longer useful to
            you and your team. This cannot be undone.
          </p>
        )}
      </DialogContent>
      <DialogActions $align="left">
        <Button
          variant="destructive"
          disabled={error != null || deleteLoading}
          onClick={onDelete}>
          Delete view
        </Button>
        <Button
          variant="ghost"
          disabled={deleteLoading}
          onClick={() => {
            setConfirmDelete(false);
            setError(null);
          }}>
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  );
};
