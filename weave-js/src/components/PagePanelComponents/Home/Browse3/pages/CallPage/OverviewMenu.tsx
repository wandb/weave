import {PopupDropdown} from '@wandb/weave/common/components/PopupDropdown';
import {Button} from '@wandb/weave/components/Button';
import {IconDelete} from '@wandb/weave/components/Icon';
import React, {FC, useState} from 'react';
import {Modal} from 'semantic-ui-react';
import styled from 'styled-components';

import {useClosePeek} from '../../context';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
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
  calls: CallSchema[];
}> = ({calls}) => {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  const closePeek = useClosePeek();

  console.log(calls);

  if (new Set(calls.map(c => c.entity)).size > 1) {
    throw new Error('Cannot delete calls from multiple entities');
  }
  const entity = calls.length > 0 ? calls[0].entity : '';

  if (new Set(calls.map(c => c.project)).size > 1) {
    throw new Error('Cannot delete calls from multiple projects');
  }
  const project = calls.length > 0 ? calls[0].project : '';

  const onDelete = () => {
    client
      .callsDelete({
        project_id: `${entity}/${project}`,
        ids: calls.map(c => c.callId),
      })
      .catch(e => {
        console.error(e);
        return false;
      })
      .then(res => {
        if (res) {
          setConfirmDelete(false);
          closePeek();
        } else {
          console.error('Failed to delete call');
        }
      });
  };

  const menuOptions = [
    [
      {
        key: 'delete',
        text: 'Delete',
        icon: <IconDelete style={{marginRight: '4px'}} />,
        onClick: () => setConfirmDelete(true),
        disabled: calls.length === 0,
      },
    ],
  ];

  return (
    <>
      {confirmDelete && (
        <Modal
          open={confirmDelete}
          onClose={() => setConfirmDelete(false)}
          size="tiny">
          <Modal.Header>
            Delete {calls.length > 1 ? 'calls' : 'call'}
          </Modal.Header>
          <Modal.Content>
            <p>
              Are you sure you want to delete{' '}
              {calls.length > 1 ? 'these calls' : 'this call'}?
            </p>
            {calls.slice(0, 10).map(call => (
              <CallName key={call.callId}>{call.spanName}</CallName>
            ))}
            {calls.length > 10 && (
              <p style={{marginTop: '8px'}}>and {calls.length - 10} more...</p>
            )}
          </Modal.Content>
          <Modal.Actions>
            <Button
              onClick={() => {
                setConfirmDelete(false);
              }}>
              Cancel
            </Button>
            <Button
              style={{marginLeft: '4px'}}
              variant="destructive"
              onClick={onDelete}>
              Confirm
            </Button>
          </Modal.Actions>
        </Modal>
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
