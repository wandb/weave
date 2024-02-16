import React, {useMemo} from 'react';
import styled from 'styled-components';

import {CategoryChip} from '../common/CategoryChip';
import {CallId, opNiceName} from '../common/Links';
import {StatusChip} from '../common/StatusChip';
import {
  CallSchema,
  refUriToOpVersionKey,
  useOpVersion,
} from '../wfReactInterface/interface';

export const Overview = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px 0;
`;
Overview.displayName = 'S.Overview';

export const CallName = styled.div`
  font-family: Source Sans Pro;
  font-size: 16px;
  font-weight: 600;
  line-height: 20px;
  letter-spacing: 0px;
  text-align: left;
`;
CallName.displayName = 'S.CallName';

export const CallOverview: React.FC<{
  call: CallSchema;
}> = ({call}) => {
  const opName = opNiceName(call.spanName);
  const truncatedId = call.callId.slice(-4);

  const opVersionKey = useMemo(() => {
    if (call.opVersionRef) {
      return refUriToOpVersionKey(call.opVersionRef);
    }
    return null;
  }, [call.opVersionRef]);
  const callOp = useOpVersion(opVersionKey);
  const opCategory = callOp.result?.category;

  const statusCode = call.rawSpan.status_code;

  return (
    <Overview>
      <CallName>{opName}</CallName>
      <CallId>{truncatedId}</CallId>
      {opCategory && <CategoryChip value={opCategory} />}
      <StatusChip value={statusCode} iconOnly />
    </Overview>
  );
};
