import {
  Dialog as MaterialDialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState} from 'react';
import styled from 'styled-components';

const MAX_DELETE_ROWS_TO_SHOW = 10;

interface DeleteModalProps {
  open: boolean;
  onClose: () => void;
  onDelete: () => Promise<any>;
  deleteTitleStr: string;
  deleteBodyStrs?: string[];
  onSuccess?: () => void;
}

export const DeleteModal: React.FC<DeleteModalProps> = ({
  open,
  onClose,
  onDelete,
  deleteTitleStr,
  deleteBodyStrs,
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

  const deleteBodyStrRes = deleteBodyStrs ? deleteBodyStrs : [deleteTitleStr];

  return (
    <Dialog
      open={open}
      onClose={() => {
        onClose();
        setError(null);
      }}>
      <Tailwind>
        <DialogTitle>Delete {deleteTitleStr}</DialogTitle>
        <DialogContent className="overflow-hidden">
          <div className="mb-16">
            {error != null ? (
              <p style={{color: 'red'}}>{error}</p>
            ) : (
              <p>Are you sure you want to delete?</p>
            )}
          </div>
          <span className="text-md mt-10 font-semibold">
            {deleteBodyStrRes
              .slice(0, MAX_DELETE_ROWS_TO_SHOW)
              .map((str, i) => (
                <div key={i}>
                  <span>{str}</span>
                </div>
              ))}
            {deleteBodyStrRes.length > MAX_DELETE_ROWS_TO_SHOW && (
              <p className="mt-2">
                and {deleteBodyStrRes.length - MAX_DELETE_ROWS_TO_SHOW} more...
              </p>
            )}
          </span>
        </DialogContent>
        <DialogActions $align="left">
          <Button
            variant="destructive"
            disabled={error != null || deleteLoading}
            onClick={handleDelete}>
            {`Delete ${deleteTitleStr}`}
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
      </Tailwind>
    </Dialog>
  );
};

export const useShowDeleteButton = (entity: string) => {
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const viewerInfo = loadingUserInfo ? null : userInfo;
  const viewer = viewerInfo ? viewerInfo.id : null;
  const isReadonly = !viewer || !viewerInfo?.teams.includes(entity);
  return !isReadonly;
};

const Dialog = styled(MaterialDialog)`
  .MuiDialog-paper {
    min-width: 400px;
    max-width: min(800px, 90vw);
    width: auto !important;
  }
`;
Dialog.displayName = 'S.Dialog';

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
