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

export const OverflowMenu: FC<{
  entity: string;
  project: string;
  callIds: string[];
  callNames: string[];
  setIsRenaming: (isEditing: boolean) => void;
}> = ({entity, project, callIds, callNames, setIsRenaming}) => {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const menuOptions = [
    [
      {
        key: 'rename',
        text: 'Rename',
        icon: <IconPencilEdit style={{marginRight: '4px'}} />,
        onClick: () => setIsRenaming(true),
        disabled: callIds.length === 0,
      },
    ],
    [
      {
        key: 'delete',
        text: 'Delete',
        icon: <IconDelete style={{marginRight: '4px'}} />,
        onClick: () => setConfirmDelete(true),
        disabled: callIds.length === 0,
      },
    ],
  ];

  return (
    <>
      {confirmDelete && (
        <ConfirmDeleteModal
          entity={entity}
          project={project}
          callIds={callIds}
          callNames={callNames}
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

const ConfirmDeleteModal: FC<{
  entity: string;
  project: string;
  callIds: string[];
  callNames: string[];
  confirmDelete: boolean;
  setConfirmDelete: (confirmDelete: boolean) => void;
}> = ({
  entity,
  project,
  callIds,
  callNames,
  confirmDelete,
  setConfirmDelete,
}) => {
  const {useCallsDeleteFunc} = useWFHooks();
  const callsDelete = useCallsDeleteFunc();
  const closePeek = useClosePeek();

  const [deleteLoading, setDeleteLoading] = useState(false);

  const [error, setError] = useState(
    callIds.length === 0 ? 'No call(s) selected' : null
  );

  const onDelete = () => {
    setDeleteLoading(true);
    callsDelete(`${entity}/${project}`, callIds)
      .catch(() => {
        setError(`Failed to delete call(s) ${callNames.join(', ')}`);
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
      <DialogTitle>Delete {callIds.length > 1 ? 'calls' : 'call'}</DialogTitle>
      <DialogContent>
        {error != null ? (
          <p style={{color: 'red'}}>{error}</p>
        ) : (
          <p>
            Are you sure you want to delete
            {callIds.length > 1 ? ' these calls' : ' this call'}?
          </p>
        )}
        {callNames
          .slice(0, MAX_DELETED_CALLS_TO_SHOW)
          .map((callName, index) => (
            <CallName key={callIds[index]}>{callName}</CallName>
          ))}
        {callNames.length > MAX_DELETED_CALLS_TO_SHOW && (
          <p style={{marginTop: '8px'}}>
            and {callNames.length - MAX_DELETED_CALLS_TO_SHOW} more...
          </p>
        )}
      </DialogContent>
      <DialogActions $align="left">
        <Button
          variant="destructive"
          disabled={error != null || deleteLoading}
          onClick={onDelete}>
          {callIds.length > 1 ? 'Delete calls' : 'Delete call'}
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
