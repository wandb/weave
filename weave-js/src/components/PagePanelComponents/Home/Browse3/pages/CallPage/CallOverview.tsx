import React, {SyntheticEvent} from 'react';
import styled from 'styled-components';

import EditableField from '../../../../../../common/components/EditableField';
import {makeRefCall} from '../../../../../../util/refs';
import {Reactions} from '../../feedback/Reactions';
import {EditableCallName} from '../common/EditableCallName';
import {CopyableId} from '../common/Id';
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

export const Spacer = styled.div`
  flex: 1 1 auto;
`;
Spacer.displayName = 'S.Spacer';

export const OverflowBin = styled.div`
  align-items: right;
  margin-left: auto;
`;
OverflowBin.displayName = 'S.OverflowBin';

export const CallOverview: React.FC<{
  call: CallSchema;
}> = ({call}) => {
  const statusCode = call.rawSpan.status_code;
  const refCall = makeRefCall(call.entity, call.project, call.callId);
  const editableCallDisplayNameRef = React.useRef<EditableField>(null);

  return (
    <>
      <Overview>
        <CallName>
          <EditableCallName
            call={call}
            editableFieldRef={editableCallDisplayNameRef}
          />
        </CallName>
        <CopyableId id={call.callId} type="Call" />
        <StatusChip value={statusCode} iconOnly />
        <Spacer />
        <Reactions weaveRef={refCall} forceVisible={true} />
        <OverflowBin>
          <OverflowMenu
            selectedCalls={[call]}
            setIsRenaming={() => {
              editableCallDisplayNameRef.current?.startEditing(
                new MouseEvent('click') as unknown as SyntheticEvent
              );
            }}
          />
        </OverflowBin>
      </Overview>
      {call.rawSpan.exception && (
        <ExceptionAlert exception={call.rawSpan.exception} />
      )}
    </>
  );
};
