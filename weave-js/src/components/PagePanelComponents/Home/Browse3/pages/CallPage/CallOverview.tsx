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
  showFeedback?: boolean;
  onToggleFeedback?: () => void;
}> = ({call, showFeedback, onToggleFeedback}) => {
  const statusCode = call.rawSpan.status_code;
  const refCall = makeRefCall(call.entity, call.project, call.callId);
  const editableCallDisplayNameRef = React.useRef<EditableField>(null);
  const [isEditing, setIsEditing] = React.useState(false);

  return (
    <>
      <Overview>
        <StatusChip value={statusCode} iconOnly />
        <CallName $isEditing={isEditing}>
          <EditableCallName call={call} onEditingChange={setIsEditing} />
        </CallName>
        <CopyableId id={call.callId} type="Call" />
        <Spacer />
        <div>
          <Reactions 
            weaveRef={refCall} 
            forceVisible={true}
            showFeedback={showFeedback}
            onToggleFeedback={onToggleFeedback} 
          />
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
