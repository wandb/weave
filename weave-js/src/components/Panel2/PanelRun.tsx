import {callOpVeryUnsafe, voidNode} from '@wandb/weave/core';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {useGatedValue} from '../../hookUtils';
import * as CGReact from '../../react';
import {usePanelStacksForType} from './availablePanels';
import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';
import {Panel2Loader} from './PanelComp';

const inputType = {type: 'run-type' as const, _output: 'any' as const};
interface PanelRunConfig {
  panelConfig: any;
}

type PanelRunProps = Panel2.PanelProps<typeof inputType, PanelRunConfig>;

export const PanelRun: React.FC<PanelRunProps> = props => {
  const consoleRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<'log' | 'output'>('log');
  let runQuery = CGReact.useValue(props.input);
  runQuery = useGatedValue(runQuery, () => !runQuery.loading);
  const refresh = runQuery.refresh;
  const outputNode = useMemo(() => {
    if (runQuery.loading || runQuery.result._state._val === 'running') {
      return voidNode();
    }
    const called = callOpVeryUnsafe('run-output', {self: props.input});
    called.type = props.input.type._output;
    return called;
  }, [runQuery.loading, runQuery.result, props.input]);
  const {handler} = usePanelStacksForType(
    props.input.type._output,
    undefined,
    {}
  );
  const onScroll = useCallback(() => {
    if (consoleRef.current != null) {
      console.log('on scroll', consoleRef);
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, []);
  // Poll
  // This is wrong! All panels will set their own timers.
  // TODO: centralize
  useEffect(() => {
    onScroll();
    if (!runQuery.loading && runQuery.result._state._val !== 'finished') {
      const intervalId = setInterval(() => refresh(), 5000);
      return () => clearInterval(intervalId);
    }
    return undefined;
  }, [onScroll, runQuery.loading, runQuery.result, refresh]);
  if (runQuery.loading) {
    return <Panel2Loader />;
  }
  const run = runQuery.result;
  return (
    <div>
      <div>State: {run._state._val}</div>
      <div style={{display: 'flex', marginBottom: 8}}>
        <div
          onClick={() => setTab('log')}
          style={{
            cursor: 'pointer',
            marginRight: 8,
            borderBottom: tab === 'log' ? '1px solid black' : undefined,
          }}>
          Log
        </div>
        <div
          onClick={() => setTab('output')}
          style={{
            cursor: 'pointer',
            borderBottom: tab === 'output' ? '1px solid black' : undefined,
          }}>
          Output
        </div>
      </div>
      {tab === 'output' ? (
        outputNode.nodeType !== 'void' && handler != null ? (
          <div>
            {handler.id}
            <div
              style={{border: '1px solid #eee', padding: 6}}
              onScroll={onScroll}>
              <PanelComp2
                input={outputNode as any}
                inputType={outputNode.type}
                loading={false}
                panelSpec={handler}
                configMode={false}
                context={props.context}
                config={props.config?.panelConfig}
                updateConfig={(newPanelConfig: any) =>
                  props.updateConfig({panelConfig: newPanelConfig})
                }
                updateContext={() => {}}
              />
            </div>
          </div>
        ) : (
          <div>No panel</div>
        )
      ) : (
        <div>
          <div
            ref={consoleRef}
            style={{height: 200, border: '1px solid #eee', overflow: 'auto'}}>
            {run._prints.map(p => (
              <div
                style={{
                  fontFamily: 'monospace',
                  fontSize: 12,
                  lineHeight: 1.4,
                }}>
                {p}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'run',
  Component: PanelRun,
  inputType,
};
