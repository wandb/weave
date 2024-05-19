import {
  callOpVeryUnsafe,
  ConstNode,
  constNodeUnsafe,
  FunctionType,
  functionType,
  isFunction,
  loadRemoteOpStore,
  Node,
  NodeOrVoidNode,
  OpDef,
  OpStore,
  ServerOpDef,
  Stack,
  varNode,
  voidNode,
  Weave,
} from '@wandb/weave/core';
import {memoize} from 'lodash';
import React, {useCallback, useMemo, useRef} from 'react';

import getConfig from '../../config';
import {useGatedValue} from '../../hookUtils';
import {useNodeValue} from '../../react';
import {consoleWarn} from '../../util';
import * as Panel2 from './panel';
import {Panel, Panel2Loader} from './PanelComp';
import {
  ExpressionEvent,
  PanelContextProvider,
  usePanelContext,
} from './PanelContext';
// This file contains the implementation of a
// "pure weave panel", ie one that is defined entirely in terms of
// weave objects, with no corresponding React components.
import {makeItemNode} from './PanelGroup';
import {registerPanel} from './PanelRegistry';

const INITIALIZE_OP_SUFFIX = '-initialize';
const RENDER_OP_SUFFIX = '-render';
const RENDER_CONFIG_OP_SUFFIX = '-render_config';

interface UserPanelConfig {
  // The panel returned by the panel's config op.
  _configRenderAsPanel?: {
    id: string;
    input_node: Node;
    config: any;
  };
  // The panel returned by the panel's render op.
  _renderAsPanel?: {
    id: string;
    input_node: Node;
    config: any;
  };
  [key: string]: any;
}
type UserPanelProps = Panel2.PanelProps<'any', UserPanelConfig>;

const useUserPanelVars = (
  props: UserPanelProps,
  panelId: string,
  mode: 'config' | 'render',
  skip: boolean = false
) => {
  const {updateConfig, updateConfig2} = props;
  const initialLoading = useRef(true);
  const {stack} = usePanelContext();

  const itemNode = useMemo(
    () =>
      makeItemNode(
        {
          id: panelId,
          input_node: props.input,
          config: props.config,
          vars: {},
        },
        stack,
        undefined
      ),
    [panelId, props.config, props.input, stack]
  );

  const renderOpName = `${panelId}${
    mode === 'render' ? RENDER_OP_SUFFIX : RENDER_CONFIG_OP_SUFFIX
  }`;
  const renderAsPanelConfigAttr =
    mode === 'render' ? '_renderAsPanel' : '_configRenderAsPanel';

  const panelVars = useMemo(() => {
    return {
      self: itemNode,
    };
  }, [itemNode]);

  const handleVarEvent = useCallback(
    (varName: string, target: NodeOrVoidNode, event: ExpressionEvent) => {
      console.log('HANDLE USER PANEL VAR EVENT', varName, event);
      if (event.id === 'mutate') {
        if (varName === 'self') {
          if (updateConfig2 != null) {
            // TODO(np): newRootNode guaranteed to be ConstNode here?
            updateConfig2(() => (event.newRootNode as ConstNode).val.config);
          }
          return;
        }
      }
      consoleWarn('UserPanel Unhandled var event', varName, event, target);
    },
    [updateConfig2]
  );

  const calledRender = useMemo(() => {
    const renderOpArgs: {[key: string]: NodeOrVoidNode} = {
      // We actually pass the panel as varNode expression instead of as
      // the value. We're effectively "weavifying" the panel op here.
      // This makes it so we don't have to recall the panel on every render.
      // TODO: this should be built into the system at a deeper level.
      self: constNodeUnsafe(
        functionType({}, itemNode.type),
        varNode(itemNode.type, 'self')
      ),
    };
    return !skip && props.config?.[renderAsPanelConfigAttr] == null
      ? (callOpVeryUnsafe(renderOpName, renderOpArgs) as Node)
      : voidNode();
  }, [itemNode, props.config, renderAsPanelConfigAttr, renderOpName, skip]);
  console.log('CALLED RENDER', calledRender);
  let renderOpResult = useNodeValue(calledRender);
  // If the render op is still loading, use the previous rendered panel
  renderOpResult = useGatedValue(renderOpResult, v => !v.loading);
  if (!renderOpResult.loading) {
    initialLoading.current = false;
  }

  const renderAsPanel = useMemo(
    () =>
      // If the panel has been modified in the UI, use the modified panel config
      // instead of what would be returned by the render op
      props.config?.[renderAsPanelConfigAttr] ??
      (renderOpResult.loading
        ? {
            id: '',
            input_node: voidNode(),
            config: undefined,
          }
        : {
            id: renderOpResult.result.id,
            input_node: renderOpResult.result.input_node,
            config: renderOpResult.result.config,
          }),
    [props.config, renderAsPanelConfigAttr, renderOpResult]
  );

  const updatePanelConfig = useCallback(
    (newPanelConfig: any) => {
      updateConfig({
        [renderAsPanelConfigAttr]: {
          id: renderAsPanel.id,
          input_node: renderAsPanel.input_node,
          config: {...renderAsPanel.config, ...newPanelConfig},
        },
      });
    },
    [
      updateConfig,
      renderAsPanelConfigAttr,
      renderAsPanel.id,
      renderAsPanel.input_node,
      renderAsPanel.config,
    ]
  );
  const updatePanelConfig2 = useCallback(
    (change: <T>(oldConfig: T) => Partial<T>) => {
      if (updateConfig2 == null) {
        return;
      }
      updateConfig2((oldConfig: UserPanelConfig): UserPanelConfig => {
        const oldRenderAsPanel = oldConfig[renderAsPanelConfigAttr] ?? {
          id: renderOpResult.result.id,
          input_node: renderOpResult.result.input_node,
          config: renderOpResult.result.config,
        };
        return {
          [renderAsPanelConfigAttr]: {
            id: oldRenderAsPanel.id,
            input_node: oldRenderAsPanel.input_node,
            config: {
              ...oldRenderAsPanel.config,
              ...change(oldConfig[renderAsPanelConfigAttr]),
            },
          },
        };
      });
    },
    [renderAsPanelConfigAttr, renderOpResult.result, updateConfig2]
  );

  return useMemo(
    () => ({
      renderAsPanel,
      panelVars,
      handleVarEvent,
      updatePanelConfig,
      updatePanelConfig2,
      modified: props.config?.[renderAsPanelConfigAttr] != null,
      inputNode: renderAsPanel.input_node,
      loading: initialLoading.current,
    }),
    [
      renderAsPanel,
      panelVars,
      handleVarEvent,
      updatePanelConfig,
      updatePanelConfig2,
      props.config,
      renderAsPanelConfigAttr,
    ]
  );
};

interface PanelLikeType {
  input_node: FunctionType;
}

const isPanelType = (type: any): type is PanelLikeType => {
  return type.input_node != null && isFunction(type.input_node);
};

const registerUserPanel = (
  panelId: string,
  renderOp: ServerOpDef,
  configOp?: ServerOpDef,
  initializeOp?: OpDef
) => {
  const inputNames = Object.keys(renderOp.input_types);
  const inputTypes = Object.values(renderOp.input_types);
  const panelType = inputTypes[0];
  if (!isPanelType(panelType)) {
    consoleWarn('non-panel type for panel op: ', renderOp);
    return;
  }
  const inputNodeType = panelType.input_node;
  const inputType = inputNodeType.outputType;

  if (inputNames[1] != null && inputNames[1] !== 'config') {
    consoleWarn('panel op 2nd arg name is not "config": ', renderOp);
    return;
  }

  const ConfigComponent: React.FC<UserPanelProps> | undefined =
    configOp == null
      ? undefined
      : props => {
          console.log('RENDER CONFIG COMP', props);
          const {
            panelVars,
            handleVarEvent,
            renderAsPanel,
            updatePanelConfig,
            updatePanelConfig2,
            loading,
            inputNode,
          } = useUserPanelVars(props, panelId, 'config', false);
          console.log('RENDER CONFIG COMP', props);
          if (loading) {
            return <Panel2Loader />;
          }
          console.log('CONFIG RENDER AS PANEL', renderAsPanel);
          return (
            <PanelContextProvider
              newVars={panelVars}
              handleVarEvent={handleVarEvent}>
              <Panel
                panelSpec={renderAsPanel.id}
                input={inputNode}
                config={renderAsPanel.config}
                updateConfig={updatePanelConfig}
                updateConfig2={updatePanelConfig2}
                updateInput={props.updateInput}
              />
            </PanelContextProvider>
          );
        };
  const RenderComponent: React.FC<UserPanelProps> = props => {
    const {
      panelVars,
      handleVarEvent,
      renderAsPanel,
      updatePanelConfig,
      updatePanelConfig2,
      loading,
      inputNode,
    } = useUserPanelVars(props, panelId, 'render', false);
    if (loading) {
      return <Panel2Loader />;
    }
    console.log('RENDER AS PANEL', renderAsPanel);
    return (
      <PanelContextProvider newVars={panelVars} handleVarEvent={handleVarEvent}>
        <Panel
          panelSpec={renderAsPanel.id}
          input={inputNode}
          config={renderAsPanel.config}
          updateConfig={updatePanelConfig}
          updateConfig2={updatePanelConfig2}
          updateInput={props.updateInput}
        />
      </PanelContextProvider>
    );
  };

  let initialize;
  if (initializeOp != null) {
    initialize = async (
      weave: Weave,
      inputNode: NodeOrVoidNode,
      stack: Stack
    ) => {
      const calledInitialize = callOpVeryUnsafe(initializeOp.name, {
        self: makeItemNode(
          {
            id: panelId,
            input_node: inputNode as Node,
            config: undefined,
            vars: {},
          },
          stack,
          undefined
        ),
      });
      return await weave.client.query(calledInitialize as Node);
    };
  }

  registerPanel({
    id: panelId,
    initialize,
    ConfigComponent,
    Component: RenderComponent,
    inputType,
  });
};

const loadWeaveObjects = (): Promise<OpStore> => {
  return loadRemoteOpStore(getConfig().backendWeaveOpsUrl()).then(
    ({remoteOpStore, userPanelOps}) => {
      // For now we use the convention that config op names end with '_config'
      const renderOps: {[opName: string]: ServerOpDef} = {};
      const configOps: {[opName: string]: ServerOpDef} = {};
      const initializeOps: {[opName: string]: OpDef} = {};
      // At the moment there are two conventions:
      // Newer:
      //   <PanelType>-render, <PanelType>-config, <PanelType>-initialize
      // Older:
      //   TODO: But now this one is broken.
      //   "whatever" (is treated as render method)

      for (const op of userPanelOps) {
        if (op.name.endsWith(RENDER_CONFIG_OP_SUFFIX)) {
          configOps[
            op.name.slice(0, op.name.length - RENDER_CONFIG_OP_SUFFIX.length)
          ] = op;
        } else if (op.name.endsWith(RENDER_OP_SUFFIX)) {
          renderOps[
            op.name.slice(0, op.name.length - RENDER_OP_SUFFIX.length)
          ] = op;
        } else {
          // Old-style
          renderOps[op.name] = op;
        }
      }
      for (const op of Object.values(remoteOpStore.allOps())) {
        if (op.name.endsWith(INITIALIZE_OP_SUFFIX)) {
          initializeOps[
            op.name.slice(0, op.name.length - INITIALIZE_OP_SUFFIX.length)
          ] = op;
        }
      }
      for (const [opId, renderOp] of Object.entries(renderOps)) {
        registerUserPanel(opId, renderOp, configOps[opId], initializeOps[opId]);
      }
      return remoteOpStore;
    }
  );
};

const memoedLoadWeaveObject = memoize(loadWeaveObjects);

export const useLoadWeaveObjects = (
  skip?: boolean
):
  | {loading: true; remoteOpStore: OpStore | null}
  | {loading: false; remoteOpStore: OpStore} => {
  const [loading, setLoading] = React.useState(true);
  const [remoteOpStore, setRemoteOpStore] = React.useState<OpStore | null>(
    null
  );

  React.useEffect(() => {
    if (!skip) {
      memoedLoadWeaveObject().then(loadedRemoteOpStore => {
        setRemoteOpStore(loadedRemoteOpStore);
        setLoading(false);
      });
    }
  }, [skip]);

  if (loading || remoteOpStore == null) {
    return {loading: true, remoteOpStore};
  }
  return {loading, remoteOpStore};
};
