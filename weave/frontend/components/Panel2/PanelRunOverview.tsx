import * as globals from '@wandb/common/css/globals.styles';

import React from 'react';
import * as Panel2 from './panel';
import * as Op from '@wandb/cg/browser/ops';
import * as CG from '@wandb/cg/browser/graph';
import {PanelNumber} from './PanelNumber';
import {PanelString} from './PanelString';
import PanelDate from './PanelDate/Component';
import {PanelObjectOverview} from './PanelObjectOverview';

import styled from 'styled-components';

const inputType = 'run' as const;
type PanelRunOverviewProps = Panel2.PanelProps<typeof inputType>;

const KeyValTable = styled.div``;
const KeyValTableRow = styled.div`
  display: flex;
  align-items: flex-start;
`;
const KeyValTableKey = styled.div`
  color: ${globals.gray500};
  width: 100px;
`;
const KeyValTableVal = styled.div`
  flex-grow: 1;
`;

const InputUpdateLink = styled.div`
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
`;

export const PanelRunOverview: React.FC<PanelRunOverviewProps> = props => {
  // What if panels could take multiple inputs? Then this would be
  // props.input.run
  // Just like we can chain op graphs, we can chain panels...
  // Then why not just use regular props for calling panels. Do we
  // need inputs?
  // Multiple inputs........
  const run = props.input;
  const inputVar = CG.varNode(props.input.type, 'input');
  return (
    <KeyValTable>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(Op.opRunName({run: inputVar}) as any)
            }>
            Name
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelString
            input={Op.opRunName({run}) as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTableVal>
      </KeyValTableRow>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(Op.opRunProject({run: inputVar}) as any)
            }>
            Project
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelString
            input={Op.opProjectName({project: Op.opRunProject({run})}) as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTableVal>
      </KeyValTableRow>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(Op.opRunJobtype({run: inputVar}) as any)
            }>
            Job type
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelString
            input={Op.opRunJobtype({run}) as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTableVal>
      </KeyValTableRow>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(Op.opRunCreatedAt({run: inputVar}) as any)
            }>
            Created
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelDate
            input={Op.opRunCreatedAt({run}) as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTableVal>
      </KeyValTableRow>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(Op.opRunHeartbeatAt({run: inputVar}) as any)
            }>
            Heartbeat
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelDate
            input={Op.opRunHeartbeatAt({run}) as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTableVal>
      </KeyValTableRow>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(Op.opRunConfig({run: inputVar}) as any)
            }>
            Config
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelObjectOverview
            input={Op.opRunConfig({run}) as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTableVal>
      </KeyValTableRow>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(Op.opRunSummary({run: inputVar}) as any)
            }>
            Summary
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelObjectOverview
            input={Op.opRunSummary({run}) as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTableVal>
      </KeyValTableRow>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(Op.opRunHistory({run: inputVar}) as any)
            }>
            History
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <div style={{display: 'flex'}}>
            <div style={{marginRight: 4}}>
              <PanelNumber
                input={Op.opCount({arr: Op.opRunHistory({run})}) as any}
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => console.log('HELLO')}
              />{' '}
            </div>
            rows logged
          </div>
          <PanelObjectOverview
            input={
              Op.opIndex({
                arr: Op.opRunHistory({run}) as any,
                index: Op.constNumber(0),
              }) as any
            }
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTableVal>
      </KeyValTableRow>
    </KeyValTable>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'run-overview',
  Component: PanelRunOverview,
  inputType,
};
