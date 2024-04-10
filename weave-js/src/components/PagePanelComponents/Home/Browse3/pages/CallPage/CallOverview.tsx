import React from 'react';
import styled from 'styled-components';

import {CallId} from '../common/CallId';
import {opNiceName} from '../common/Links';
import {StatusChip} from '../common/StatusChip';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {ExceptionAlert} from './Exceptions';

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

export const CallOverview: React.FC<{
  call: CallSchema;
}> = ({call}) => {
  const opName = opNiceName(call.spanName);

  const statusCode = call.rawSpan.status_code;

  return (
    <>
      <Overview>
        <CallName>{opName}</CallName>
        <CallId callId={call.callId} />
        <StatusChip value={statusCode} iconOnly />
      </Overview>
      {call.rawSpan.exception && (
        <ExceptionAlert exception={call.rawSpan.exception} />
      )}
    </>
  );
};
