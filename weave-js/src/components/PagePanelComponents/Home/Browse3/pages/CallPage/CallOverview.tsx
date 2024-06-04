import EditableField from '@wandb/weave/common/components/EditableField';
import React, {useEffect, useState} from 'react';
import styled from 'styled-components';

import {CallId} from '../common/CallId';
import {opNiceName} from '../common/Links';
import {StatusChip} from '../common/StatusChip';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {ExceptionAlert} from './Exceptions';
import {OverflowMenu} from './OverflowMenu';

export const Overview = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
`;
Overview.displayName = 'S.Overview';

export const CallName = styled.div`
  font-family: Source Sans Pro;
  font-size: 24px;
  font-weight: 600;
  line-height: 32px;
  letter-spacing: 0px;
  text-align: left;
`;
CallName.displayName = 'S.CallName';

export const OverflowBin = styled.div`
  align-items: right;
  margin-left: auto;
`;
OverflowBin.displayName = 'S.OverflowBin';

export const CallOverview: React.FC<{
  call: CallSchema;
}> = ({call}) => {
  const opName = call.displayName ?? opNiceName(call.spanName);

  const statusCode = call.rawSpan.status_code;

  const [curOpName, setCurOpName] = useState(opName);
  useEffect(() => {
    setCurOpName(opName);
  }, [opName]);
  const {useCallRenameFunc} = useWFHooks();
  const callRename = useCallRenameFunc();

  return (
    <>
      <Overview>
        <CallName>
          <EditableField
            value={curOpName}
            save={newName => {
              callRename(
                `${call.entity}/${call.project}`,
                call.callId,
                newName
              );
              setCurOpName(newName);
            }}
            placeholder=""
            updateValue={true}
          />
        </CallName>
        <CallId callId={call.callId} />
        <StatusChip value={statusCode} iconOnly />
        <OverflowBin>
          <OverflowMenu selectedCalls={[call]} />
        </OverflowBin>
      </Overview>
      {call.rawSpan.exception && (
        <ExceptionAlert exception={call.rawSpan.exception} />
      )}
    </>
  );
};
