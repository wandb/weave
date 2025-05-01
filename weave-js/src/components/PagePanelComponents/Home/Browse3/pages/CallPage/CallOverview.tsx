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
  & > * {
    margin-right: 4px;
  }
  & > *:first-child {
    margin-right: 4px;
  }
  & > *:last-child {
    margin-right: 0px;
  }
`;
Overview.displayName = 'S.Overview';

export const CallName = styled.div<{$isEditing?: boolean}>`
  font-family: Source Sans Pro;
  font-size: 16px;
  font-weight: 600;
  text-align: left;
  min-width: 0;
  width: 100%;
`;
CallName.displayName = 'S.CallName';

export const Spacer = styled.div`
  flex: 1 1 auto;
`;
Spacer.displayName = 'S.Spacer';

export const OverflowBin = styled.div`
  align-items: right;
`;
OverflowBin.displayName = 'S.OverflowBin';

export const CallOverview: React.FC<{
  call: CallSchema;
}> = ({call}) => {
  const statusCode = call.rawSpan.status_code;
  const refCall = makeRefCall(call.entity, call.project, call.callId);
  const editableCallDisplayNameRef = React.useRef<EditableField>(null);
  const [, setIsEditing] = React.useState(false);

  return (
    <>
      <Overview>
        <StatusChip value={statusCode} iconOnly />
        <CallName>
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
