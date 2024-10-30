import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import React, {useState} from 'react';
import styled from 'styled-components';

interface DeleteModalProps {
  open: boolean;
  onClose: () => void;
  onDelete: () => Promise<void>;
  deleteTargetStr: string;
  onSuccess?: () => void;
}

export const DeleteModal: React.FC<DeleteModalProps> = ({
  open,
  onClose,
  onDelete,
  deleteTargetStr,
  onSuccess,
}) => {
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = () => {
    setDeleteLoading(true);
    onDelete()
      .then(() => {
        onClose();
        onSuccess?.();
      })
      .catch(err => {
        setError(err.message);
      })
      .finally(() => {
        setDeleteLoading(false);
      });
  };

  return (
    <Dialog
      open={open}
      onClose={() => {
        onClose();
        setError(null);
      }}
      maxWidth="xs"
      fullWidth>
      <DialogTitle>Delete {deleteTargetStr}</DialogTitle>
      <DialogContent style={{overflow: 'hidden'}}>
        {error != null ? (
          <p style={{color: 'red'}}>{error}</p>
        ) : (
          <p>Are you sure you want to delete?</p>
        )}
        <span style={{fontSize: '16px', fontWeight: '600'}}>
          {deleteTargetStr}
        </span>
      </DialogContent>
      <DialogActions $align="left">
        <Button
          variant="destructive"
          disabled={error != null || deleteLoading}
          onClick={handleDelete}>
          {`Delete ${deleteTargetStr}`}
        </Button>
        <Button
          variant="ghost"
          disabled={deleteLoading}
          onClick={() => {
            onClose();
            setError(null);
          }}>
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  );
};

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
