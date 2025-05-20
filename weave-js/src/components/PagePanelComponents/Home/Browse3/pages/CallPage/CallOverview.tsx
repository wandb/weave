import React, {SyntheticEvent} from 'react';
import styled from 'styled-components';

import EditableField from '../../../../../../common/components/EditableField';
import {makeRefCall} from '../../../../../../util/refs';
import {Reactions} from '../../feedback/Reactions';
import {EditableCallName} from '../common/EditableCallName';
import {CopyableId} from '../common/Id';
import {StatusChip} from '../common/StatusChip';
import {ComputedCallStatuses} from '../wfReactInterface/traceServerClientTypes';
import {traceCallStatusCode} from '../wfReactInterface/tsDataModelHooks';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {ExceptionAlert} from './Exceptions';
import {OverflowMenu} from './OverflowMenu';

export const Overview = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;
Overview.displayName = 'S.Overview';

export const CallName = styled.div<{$isEditing?: boolean}>`
  font-family: Source Sans Pro;
  font-size: 16px;
  font-weight: 600;
  text-align: left;
  word-break: break-all;
  width: ${props => (props.$isEditing ? '100%' : 'max-content%')};
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
  const refCall = makeRefCall(call.entity, call.project, call.callId);
  const editableCallDisplayNameRef = React.useRef<EditableField>(null);
  const [isEditing, setIsEditing] = React.useState(false);

  const status = call.traceCall
    ? traceCallStatusCode(call.traceCall)
    : ComputedCallStatuses.running;

  return (
    <>
      <Overview>
        <StatusChip value={status} iconOnly />
        <CallName $isEditing={isEditing}>
          <EditableCallName call={call} onEditingChange={setIsEditing} />
        </CallName>
        <CopyableId id={call.callId} type="Call" />
        <Spacer />
        <div>
          <Reactions weaveRef={refCall} forceVisible={true} />
        </div>
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
