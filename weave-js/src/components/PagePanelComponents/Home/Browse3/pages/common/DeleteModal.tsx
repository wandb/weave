import {
  Dialog as MaterialDialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState} from 'react';
import styled from 'styled-components';

import {useClosePeek} from '../../context';
import {useWFHooks} from '../wfReactInterface/context';
import {
  ObjectVersionSchema,
  OpVersionSchema,
} from '../wfReactInterface/wfDataModelHooksInterface';

interface DeleteModalProps {
  open: boolean;
  onClose: () => void;
  onDelete: () => Promise<void>;
  deleteTargetStr: string;
  onSuccess?: () => void;
}

const Dialog = styled(MaterialDialog)`
  .MuiDialog-paper {
    min-width: 400px;
    max-width: min(800px, 90vw);
    width: auto !important;
  }
`;

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
      }}>
      <Tailwind>
        <DialogTitle>Delete {deleteTargetStr}</DialogTitle>
        <DialogContent className="overflow-hidden">
          <div className="mb-16">
            {error != null ? (
              <p style={{color: 'red'}}>{error}</p>
            ) : (
              <p>Are you sure you want to delete?</p>
            )}
          </div>
          <span className="text-md mt-10 font-semibold">{deleteTargetStr}</span>
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
      </Tailwind>
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

export const DeleteObjectButtonWithModal: React.FC<{
  objVersionSchema: OpVersionSchema | ObjectVersionSchema;
  overrideDisplayStr?: string;
}> = ({objVersionSchema, overrideDisplayStr}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const closePeek = useClosePeek();
  const {opVersionDelete, objectVersionDelete} = useObjectDeleteFunc();
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const doDelete = () => {
    if (versionSchemaIsOp(objVersionSchema)) {
      return opVersionDelete(objVersionSchema);
    }
    return objectVersionDelete(objVersionSchema);
  };

  const deleteStr =
    overrideDisplayStr ?? makeDefaultObjectDeleteStr(objVersionSchema);

  return (
    <>
      <Button
        icon="delete"
        variant="ghost"
        onClick={() => setDeleteModalOpen(true)}
      />
      <DeleteModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        deleteTargetStr={deleteStr}
        onDelete={doDelete}
        onSuccess={closePeek}
      />
    </>
  );
};

function versionSchemaIsOp(
  objVersionSchema: OpVersionSchema | ObjectVersionSchema
) {
  return 'opId' in objVersionSchema;
}

function makeDefaultObjectDeleteStr(
  objVersionSchema: OpVersionSchema | ObjectVersionSchema
) {
  if (versionSchemaIsOp(objVersionSchema)) {
    return `${objVersionSchema.opId}:v${objVersionSchema.versionIndex}`;
  }
  return `${objVersionSchema.objectId}:v${objVersionSchema.versionIndex}`;
}
