import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {Button} from '@wandb/weave/components/Button';
import {IconDelete} from '@wandb/weave/components/Icon';
import React, {FC, useState} from 'react';
import styled from 'styled-components';

import {useClosePeek} from '../../context';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import { useHistory } from 'react-router-dom';

export const OverflowMenu: FC<{
  selectedCalls: CallSchema[];
  refetch?: () => void;
}> = ({selectedCalls, refetch}) => {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const menuOptions = [
    [
      {
        key: 'delete',
        text: 'Delete',
        icon: <IconDelete style={{marginRight: '4px'}} />,
        onClick: () => setConfirmDelete(true),
        disabled: selectedCalls.length === 0,
      },
    ],
  ];

  return (
    <>
      {confirmDelete && (
        <ConfirmDeleteModal
          calls={selectedCalls}
          confirmDelete={confirmDelete}
          setConfirmDelete={setConfirmDelete}
          refetch={refetch}
        />
      )}
      <PopupDropdown
        sections={menuOptions}
        trigger={
          <Button
            className="row-actions-button"
            icon="overflow-horizontal"
            size="medium"
            variant="ghost"
            style={{marginLeft: '4px'}}
          />
        }
        offset="-68px, -10px"
      />
    </>
  );
};

const CallName = styled.p`
  font-size: 16px;
  line-height: 18px;
  font-weight: 600;
  letter-spacing: 0px;
  text-align: left;
`;
CallName.displayName = 'S.CallName';

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

const MAX_DELETED_CALLS_TO_SHOW = 10;

const ConfirmDeleteModal: FC<{
  calls: CallSchema[];
  confirmDelete: boolean;
  setConfirmDelete: (confirmDelete: boolean) => void;
  refetch?: () => void;
}> = ({calls, confirmDelete, setConfirmDelete, refetch}) => {
  const {useCallsDeleteFunc} = useWFHooks();
  const callsDelete = useCallsDeleteFunc();
  const closePeek = useClosePeek();

  const [deleteLoading, setDeleteLoading] = useState(false);

  let error = null;
  if (calls.length === 0) {
    error = 'No calls selected';
  } else if (new Set(calls.map(c => c.entity)).size > 1) {
    error = 'Cannot delete calls from multiple entities';
  } else if (new Set(calls.map(c => c.project)).size > 1) {
    error = 'Cannot delete calls from multiple projects';
  }

  const onDelete = () => {
    setDeleteLoading(true);
    callsDelete(
      `${calls[0].entity}/${calls[0].project}`,
      calls.map(c => c.callId)
    ).then(() => {
      setDeleteLoading(false);
      setConfirmDelete(false);
      closePeek();
    });
  };

  return (
    <Dialog
      open={confirmDelete}
      onClose={() => setConfirmDelete(false)}
      maxWidth="xs"
      fullWidth>
      <DialogTitle>Delete {calls.length > 1 ? 'calls' : 'call'}</DialogTitle>
      <DialogContent>
        {error != null ? (
          <p style={{color: 'red'}}>{error}</p>
        ) : (
          <p>
            Are you sure you want to delete
            {calls.length > 1 ? ' these calls' : ' this call'}?
          </p>
        )}
        {calls.slice(0, MAX_DELETED_CALLS_TO_SHOW).map(call => (
          <CallName key={call.callId}>{call.spanName}</CallName>
        ))}
        {calls.length > MAX_DELETED_CALLS_TO_SHOW && (
          <p style={{marginTop: '8px'}}>
            and {calls.length - MAX_DELETED_CALLS_TO_SHOW} more...
          </p>
        )}
      </DialogContent>
      <DialogActions $align="left">
        <Button
          variant="destructive"
          disabled={error != null || deleteLoading}
          onClick={onDelete}>
          {calls.length > 1 ? 'Delete calls' : 'Delete call'}
        </Button>
        <Button
          variant="ghost"
          disabled={deleteLoading}
          onClick={() => setConfirmDelete(false)}>
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  );
};
