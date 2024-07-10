import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {Button} from '@wandb/weave/components/Button';
import {IconDelete, IconPencilEdit} from '@wandb/weave/components/Icon';
import React, {FC, useState} from 'react';
import styled from 'styled-components';

import {useClosePeek} from '../../context';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

export const OverflowMenu: FC<{
  entity: string;
  project: string;
  selectedCalls: CallSchema[];
  setIsRenaming: (isEditing: boolean) => void;
}> = ({selectedCalls, setIsRenaming, entity, project}) => {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const menuOptions = [
    [
      {
        key: 'rename',
        text: 'Rename',
        icon: <IconPencilEdit style={{marginRight: '4px'}} />,
        onClick: () => setIsRenaming(true),
        disabled: selectedCalls.length !== 1,
      },
    ],
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
          entity={entity}
          project={project}
          calls={selectedCalls.map(call => ({
            callId: call.callId,
            name: call.displayName ?? call.spanName,
          }))}
          confirmDelete={confirmDelete}
          setConfirmDelete={setConfirmDelete}
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

export const ConfirmDeleteModal: FC<{
  entity: string;
  project: string;
  calls: Array<{callId: string; name: string}>;
  confirmDelete: boolean;
  setConfirmDelete: (confirmDelete: boolean) => void;
}> = ({entity, project, calls, confirmDelete, setConfirmDelete}) => {
  const {useCallsDeleteFunc} = useWFHooks();
  const callsDelete = useCallsDeleteFunc();
  const closePeek = useClosePeek();

  const [deleteLoading, setDeleteLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const onDelete = () => {
    if (calls.length === 0) {
      setError('No call(s) selected');
      return;
    }
    setDeleteLoading(true);
    callsDelete(
      entity,
      project,
      calls.map(call => call.callId)
    )
      .catch(() => {
        setError(
          `Failed to delete call(s) ${calls.map(call => call.name).join(', ')}`
        );
      })
      .then(() => {
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
      <DialogContent style={{overflow: 'hidden'}}>
        {error != null ? (
          <p style={{color: 'red'}}>{error}</p>
        ) : (
          <p>
            Are you sure you want to delete
            {calls.length > 1 ? ' these calls' : ' this call'}?
          </p>
        )}
        {calls.slice(0, MAX_DELETED_CALLS_TO_SHOW).map(call => (
          <CallName key={call.callId}>{call.name}</CallName>
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
