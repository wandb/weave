import React from 'react';
import makeComp from '@wandb/common/util/profiler';
import {useMemo, useCallback, useState, useEffect} from 'react';
import {useGatedValue} from '@wandb/common/state/hooks';
import {Panel} from './Panel2/PanelComp';
import {loadWeaveObjects} from './Panel2/weaveBackend';
import * as Panel2 from './Panel2/panel';
import * as Graph from '@wandb/cg/browser/graph';
import {
  Spec as PanelExpressionSpec,
  PanelExpressionConfig,
} from './Panel2/PanelExpression';

import Loader from '@wandb/common/components/WandbLoader';
import * as CGReact from '@wandb/common/cgreact';
import * as CGParser from '@wandb/cg/browser/parser';

const PanelWeave: React.FC = makeComp(
  props => {
    const urlParams = new URLSearchParams(window.location.search);
    const fullScreen = urlParams.get('fullScreen') != null;
    const parse = CGReact.useClientBound(CGParser.parseCG);
    const expString = urlParams.get('exp');
    const expNode = urlParams.get('expNode');
    const panelId = urlParams.get('panelId');
    const debugHello = urlParams.get('hello');
    let panelConfig = urlParams.get('panelConfig');
    const [loading, setLoading] = useState(true);
    if (panelConfig != null) {
      panelConfig = JSON.parse(panelConfig);
    }

    const [config, setConfig] = useState<PanelExpressionConfig>(
      undefined as any
    );
    const updateConfig = useCallback<any>(
      (newConfig: any) => {
        setConfig({...config, ...newConfig});
      },
      [config]
    );

    useEffect(() => {
      // eslint-disable-next-line wandb/no-unprefixed-urls
      loadWeaveObjects().then(() => {
        if (expString != null) {
          parse(expString, {}).then(res => {
            console.log('PARSED', expString, res);

            updateConfig({exp: res as any, panelId, panelConfig} as any);
            setLoading(false);
          });
        } else if (expNode != null) {
          updateConfig({
            exp: JSON.parse(expNode) as any,
            panelId,
            panelConfig,
          } as any);
          setLoading(false);
        } else {
          updateConfig({
            exp: Graph.voidNode(),
            panelId,
            panelConfig,
          } as any);
          setLoading(false);
        }
      });
    }, []);

    const [context, setContext] = useState<Panel2.PanelContext>({path: []});
    const updateContext = useCallback<Panel2.UpdateContext>(
      newContext => {
        setContext({...context, ...newContext});
      },
      [context]
    );

    const position = fullScreen ? 'fixed' : 'absolute';

    if (debugHello) {
      return <p>Hello !</p>;
    }
    const memoedInput = useMemo(() => {
      return Graph.voidNode();
    }, []);

    const updatePanelConfig = useCallback(
      (newPanelConfig: any) => {
        updateConfig({
          ...config,
          ...newPanelConfig,
        });
      },
      [config, updateConfig]
    );

    return useGatedValue(
      <div
        style={{
          position,
          backgroundColor: '#fff',
          top: 0,
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 500000,
        }}>
        {loading ? (
          <Loader />
        ) : config.exp.nodeType === 'void' ? (
          panelId === null ? (
            <div>
              Invalid PagePanel configuration, expNode or PanelId must be passed
              via URL Param
            </div>
          ) : (
            <Panel
              panelSpec={panelId}
              input={config.exp}
              config={config.panelConfig}
              updateConfig={updatePanelConfig}
            />
          )
        ) : (
          <PanelExpressionSpec.Component
            input={memoedInput as any}
            loading={false}
            configMode={false}
            context={context}
            config={config}
            updateConfig={updateConfig}
            updateContext={updateContext}
          />
        )}
      </div>,
      o => !loading
    );
  },
  {id: 'PanelWeave'}
);

export default PanelWeave;
