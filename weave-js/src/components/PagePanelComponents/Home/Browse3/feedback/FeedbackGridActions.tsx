import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import React, {useEffect, useState} from 'react';
import styled from 'styled-components';

import {Button} from '../../../../Button';
import {useGetTraceServerClientContext} from '../pages/wfReactInterface/traceServerClientContext';

type FeedbackGridActionsProps = {
  projectId: string;
  feedbackId: string;
};

export const FeedbackGridActions = ({
  projectId,
  feedbackId,
}: FeedbackGridActionsProps) => {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <>
      <Button
        size="small"
        variant="ghost"
        icon="delete"
        onClick={() => setConfirmDelete(true)}
      />
      {confirmDelete && (
        <ConfirmDeleteModal
          projectId={projectId}
          feedbackId={feedbackId}
          confirmDelete={confirmDelete}
          setConfirmDelete={setConfirmDelete}
        />
      )}
    </>
  );
};

// TODO: Move to a common place
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

type ConfirmDeleteModalProps = {
  projectId: string;
  feedbackId: string;
  confirmDelete: boolean;
  setConfirmDelete: (confirmDelete: boolean) => void;
};

export const ConfirmDeleteModal = ({
  projectId,
  feedbackId,
  confirmDelete,
  setConfirmDelete,
}: ConfirmDeleteModalProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const getTsClient = useGetTraceServerClientContext();

  useEffect(() => {
    let isMounted = true;

    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        getTsClient().feedbackPurge({
          project_id: projectId,
          query: {
            $expr: {
              $eq: [{$getField: 'id'}, {$literal: feedbackId}],
            },
          },
        });
      } catch (error) {
        if (isMounted) {
          setError('Failed to delete feedback');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    if (isRunning) {
      fetchData();
    }

    return () => {
      isMounted = false;
    };
  }, [isRunning, getTsClient, projectId, feedbackId]);

  const onDelete = () => {
    setIsRunning(true);
  };

  return (
    <Dialog
      open={confirmDelete}
      onClose={() => {
        setConfirmDelete(false);
        setError(null);
      }}
      maxWidth="xs"
      fullWidth>
      <DialogTitle>Delete feedback</DialogTitle>
      <DialogContent style={{overflow: 'hidden'}}>
        {error != null ? (
          <p style={{color: 'red'}}>{error}</p>
        ) : (
          <p>Are you sure you want to delete this feedback?</p>
        )}
      </DialogContent>
      <DialogActions $align="left">
        <Button
          variant="destructive"
          disabled={error != null || isLoading}
          onClick={onDelete}>
          Delete feedback
        </Button>
        <Button
          variant="ghost"
          disabled={isLoading}
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
