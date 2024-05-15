import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {Button} from '@wandb/weave/components/Button';
import {IconDelete} from '@wandb/weave/components/Icon';
import React, {Dispatch, FC, SetStateAction, useState} from 'react';
import {Modal} from 'semantic-ui-react';
import styled from 'styled-components';

import {useClosePeek} from '../../context';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';

const CallName = styled.p`
  font-size: 16px;
  line-height: 18px;
  font-weight: 600;
  letter-spacing: 0px;
  text-align: left;
`;
CallName.displayName = 'S.CallName';

export const OverflowMenu: FC<{
  selectedCalls: CallSchema[];
  setSelectedCalls?: Dispatch<SetStateAction<CallSchema[]>>;
  refetch?: () => void;
}> = ({selectedCalls, setSelectedCalls, refetch}) => {
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
          setSelectedCalls={setSelectedCalls}
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

const MAX_DELETED_CALLS_TO_SHOW = 10;

const ConfirmDeleteModal: FC<{
  calls: CallSchema[];
  confirmDelete: boolean;
  setConfirmDelete: (confirmDelete: boolean) => void;
  setSelectedCalls?: Dispatch<SetStateAction<CallSchema[]>>;
  refetch?: () => void;
}> = ({calls, confirmDelete, setConfirmDelete, setSelectedCalls, refetch}) => {
  const {useCallsDelete} = useWFHooks();
  const callsDelete = useCallsDelete();
  const closePeek = useClosePeek();

  if (new Set(calls.map(c => c.entity)).size > 1) {
    throw new Error('Cannot delete calls from multiple entities');
  }
  const entity = calls.length > 0 ? calls[0].entity : '';

  if (new Set(calls.map(c => c.project)).size > 1) {
    throw new Error('Cannot delete calls from multiple projects');
  }
  const project = calls.length > 0 ? calls[0].project : '';

  const onDelete = () => {
    callsDelete(
      `${entity}/${project}`,
      calls.map(c => c.callId)
    );
    setConfirmDelete(false);
    refetch?.();
    setSelectedCalls?.(curCalls => curCalls?.filter(c => !calls.includes(c)));
    closePeek();
  };

  return (
    <Modal
      open={confirmDelete}
      onClose={() => setConfirmDelete(false)}
      size="tiny">
      <Modal.Header>Delete {calls.length > 1 ? 'calls' : 'call'}</Modal.Header>
      <Modal.Content>
        <p>
          Are you sure you want to delete
          {calls.length > 1 ? ' these calls' : ' this call'}?
        </p>
        {calls.slice(0, MAX_DELETED_CALLS_TO_SHOW).map(call => (
          <CallName key={call.callId}>{call.spanName}</CallName>
        ))}
        {calls.length > MAX_DELETED_CALLS_TO_SHOW && (
          <p style={{marginTop: '8px'}}>
            and {calls.length - MAX_DELETED_CALLS_TO_SHOW} more...
          </p>
        )}
      </Modal.Content>
      <Modal.Actions>
        <Button
          variant="ghost"
          onClick={() => {
            setConfirmDelete(false);
          }}>
          Cancel
        </Button>
        <Button
          style={{marginLeft: '4px'}}
          variant="destructive"
          onClick={onDelete}>
          {calls.length > 1 ? 'Delete calls' : 'Delete call'}
        </Button>
      </Modal.Actions>
    </Modal>
  );
};
