import React, {useState} from 'react';
import styled from 'styled-components';

import {CallId} from '../common/CallId';
import {EditableCallName} from '../common/EditableCallName';
import {opNiceName} from '../common/Links';
import {StatusChip} from '../common/StatusChip';
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
  const [isRenamingCall, setIsRenamingCall] = useState<boolean | undefined>(
    undefined
  );
  const opName = call.displayName ?? opNiceName(call.spanName);

  const statusCode = call.rawSpan.status_code;

  return (
    <>
      <Overview>
        <CallName>
          <EditableCallName
            opName={opName}
            entity={call.entity}
            project={call.project}
            callId={call.callId}
            onSave={() => setIsRenamingCall(undefined)}
            externalEditingControl={isRenamingCall}
          />
        </CallName>
        <CallId callId={call.callId} />
        <StatusChip value={statusCode} iconOnly />
        <OverflowBin>
          <OverflowMenu
            entity={call.entity}
            project={call.project}
            callIds={[call.callId]}
            callNames={[opName]}
            setIsRenaming={setIsRenamingCall}
          />
        </OverflowBin>
      </Overview>
      {call.rawSpan.exception && (
        <ExceptionAlert exception={call.rawSpan.exception} />
      )}
    </>
  );
};
