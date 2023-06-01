import * as globals from '@wandb/weave/common/css/globals.styles';
import {
  constNumber,
  opCount,
  opIndex,
  opProjectName,
  opRunConfig,
  opRunCreatedAt,
  opRunHeartbeatAt,
  opRunHistory,
  opRunJobtype,
  opRunName,
  opRunProject,
  opRunSummary,
  varNode,
} from '@wandb/weave/core';
import React from 'react';
import styled from 'styled-components';

import * as Panel2 from './panel';
import PanelDate from './PanelDate/Component';
import {PanelNumber} from './PanelNumber';
import {PanelObjectOverview} from './PanelObjectOverview';
import {PanelString} from './PanelString';

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
  const inputVar = varNode(props.input.type, 'input');
  return (
    <KeyValTable>
      <KeyValTableRow>
        <KeyValTableKey>
          <InputUpdateLink
            onClick={() =>
              props.updateInput?.(opRunName({run: inputVar}) as any)
            }>
            Name
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelString
            input={opRunName({run}) as any}
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
              props.updateInput?.(opRunProject({run: inputVar}) as any)
            }>
            Project
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelString
            input={opProjectName({project: opRunProject({run})}) as any}
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
              props.updateInput?.(opRunJobtype({run: inputVar}) as any)
            }>
            Job type
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelString
            input={opRunJobtype({run}) as any}
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
              props.updateInput?.(opRunCreatedAt({run: inputVar}) as any)
            }>
            Created
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelDate
            input={opRunCreatedAt({run}) as any}
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
              props.updateInput?.(opRunHeartbeatAt({run: inputVar}) as any)
            }>
            Heartbeat
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelDate
            input={opRunHeartbeatAt({run}) as any}
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
              props.updateInput?.(opRunConfig({run: inputVar}) as any)
            }>
            Config
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelObjectOverview
            input={opRunConfig({run}) as any}
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
              props.updateInput?.(opRunSummary({run: inputVar}) as any)
            }>
            Summary
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <PanelObjectOverview
            input={opRunSummary({run}) as any}
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
              props.updateInput?.(opRunHistory({run: inputVar}) as any)
            }>
            History
          </InputUpdateLink>
        </KeyValTableKey>
        <KeyValTableVal>
          <div style={{display: 'flex'}}>
            <div style={{marginRight: 4}}>
              <PanelNumber
                input={opCount({arr: opRunHistory({run})}) as any}
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
              opIndex({
                arr: opRunHistory({run}) as any,
                index: constNumber(0),
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
