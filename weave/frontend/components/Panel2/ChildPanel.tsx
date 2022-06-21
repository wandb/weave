import React from 'react';
import * as Graph from '@wandb/cg/browser/graph';
import * as Code from '@wandb/cg/browser/code';
import * as Types from '@wandb/cg/browser/model/types';
import * as HL from '@wandb/cg/browser/hl';
import {useMemo, useCallback} from 'react';
import {PanelContextProvider, usePanelContext} from './PanelContext';
import {usePanelStacksForType} from './availablePanels';
import {Panel} from './PanelComp';
import {NodeOrVoidNode} from '@wandb/cg/browser/model/types';
import makeComp from '@wandb/common/util/profiler';

// This could be rendered as a code block with assignments, like
// so.
// ```
// a = input + 4; // will be in scope of descendent panels
// return PanelWhatever(a / 2, panel_whatever_config)
// ```
interface ChildPanelFullConfig {
  assignments: Code.Frame;
  panelInputExpr: NodeOrVoidNode;
  panelId: string;
  panelConfig: any;
}
export type ChildPanelConfig =
  | undefined
  | ChildPanelFullConfig
  | NodeOrVoidNode;
const CHILD_PANEL_DEFAULT_CONFIG: ChildPanelConfig = {
  assignments: {},
  panelInputExpr: Graph.voidNode(),
  panelId: '',
  panelConfig: undefined,
};
const useChildPanelConfig = (
  config: ChildPanelConfig
): ChildPanelFullConfig => {
  return useMemo(() => {
    if (config === undefined) {
      return CHILD_PANEL_DEFAULT_CONFIG;
    } else if (Types.isNodeOrVoidNode(config)) {
      return {...CHILD_PANEL_DEFAULT_CONFIG, panelInputExpr: config};
    } else {
      return config;
    }
  }, [config]);
};

// This is the standard way to render subpanels. We should migrate
// other cases to this (Table cell, SelectPanel in Facet, and probably
// PanelExpression and PanelRootQuery)
export const ChildPanel: React.FC<{
  config: ChildPanelConfig | undefined;
  updateConfig(newConfig: ChildPanelConfig): void;
}> = makeComp(
  props => {
    const config = useChildPanelConfig(props.config);
    const {updateConfig} = props;
    const {assignments, panelInputExpr, panelId, panelConfig} = config;
    const {frame} = usePanelContext();
    const newFrame = useMemo(
      () => ({...frame, ...assignments}),
      [frame, assignments]
    );
    const panelInput = useMemo(
      () => HL.callFunction(panelInputExpr, newFrame),
      [panelInputExpr, newFrame]
    );
    const {handler, curPanelId} = usePanelStacksForType(
      panelInput.type,
      panelId
    );

    const updatePanelConfig = useCallback(
      newPanelConfig =>
        updateConfig({
          ...config,
          panelConfig: {...config.panelConfig, ...newPanelConfig},
        }),

      [config, updateConfig]
    );

    return curPanelId == null || handler == null ? (
      <div>No panel for type {Types.toString(panelInput.type)}</div>
    ) : (
      <PanelContextProvider newVars={assignments}>
        <Panel
          input={panelInput}
          panelSpec={handler}
          config={panelConfig}
          updateConfig={updatePanelConfig}
        />
      </PanelContextProvider>
    );
  },
  {id: 'ChildPanel'}
);
