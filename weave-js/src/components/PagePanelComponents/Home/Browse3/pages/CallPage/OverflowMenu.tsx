import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {Button} from '@wandb/weave/components/Button';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {IconDelete, IconPencilEdit} from '@wandb/weave/components/Icon';
import React, {FC, useState} from 'react';
import styled from 'styled-components';

import {useClosePeek} from '../../context';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const OverflowMenu: FC<{
  selectedCalls: CallSchema[];
}> = ({selectedCalls}) => {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [renameCall, setRenameCall] = useState(false);

  const menuOptions = [
    [
      {
        key: 'rename',
        text: 'Rename',
        icon: <IconPencilEdit style={{marginRight: '4px'}} />,
        onClick: () => setRenameCall(true),
        disabled: selectedCalls.length === 0,
      },
    ], [
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
        />
      )}
      {renameCall && (
        <RenameCallModal
          calls={selectedCalls}
          renameCall={renameCall}
          setRenameCall={setRenameCall}
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
        offset="-78px, -16px"
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
}> = ({calls, confirmDelete, setConfirmDelete}) => {
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

const RenameCallModal: FC<{
  calls: CallSchema[];
  renameCall: boolean;
  setRenameCall: (renameCall: boolean) => void;
}> = ({calls, renameCall, setRenameCall}) => {
  const {useCallRenameFunc} = useWFHooks();
  const callRename = useCallRenameFunc();
  const closePeek = useClosePeek();

  let error = null;
  if (calls.length === 0) {
    error = 'No calls selected';
  } else if (calls.length > 1) {
    error = 'Cannot rename multiple calls';
  }

  const [renameLoading, setRenameLoading] = useState(false);
  const [newName, setNewName] = useState('');

  const onRename = () => {
    setRenameLoading(true);
    // Assuming renameCall is an API call or method that handles the renaming logic
    callRename(
      `${calls[0].entity}/${calls[0].project}`,
      calls[0].callId,
      newName
    )
      .then(() => {
        setRenameLoading(false);
        setRenameCall(false);
        closePeek();
      })
      .catch(e => {
        console.error('Error renaming call:', e);
        setRenameLoading(false);
      });
  };

  return (
    <>
      <Dialog
        open={renameCall}
        onClose={() => setRenameCall(false)}
        maxWidth="xs"
        fullWidth>
        <DialogTitle>Rename call</DialogTitle>
        {error != null && <p style={{color: 'red'}}>{error}</p>}
        <DialogContent>
          <TextField
            placeholder="name"
            value={newName}
            onChange={value => setNewName(value)}
            disabled={renameLoading}
            autoFocus={true}
          />
        </DialogContent>
        <DialogActions $align="left">
          <Button
            variant="primary"
            disabled={renameLoading || newName.trim() === '' || error != null}
            onClick={onRename}>
            Rename
          </Button>
          <Button
            variant="ghost"
            disabled={renameLoading}
            onClick={() => setRenameCall(false)}>
            Cancel
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};
