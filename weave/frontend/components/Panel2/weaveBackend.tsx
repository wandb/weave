import React from 'react';
import {useCallback, useMemo} from 'react';

import {backendWeaveHost} from '@wandb/common/config';
import * as CGTypes from '@wandb/cg/browser/types';
import * as Graph from '@wandb/cg/browser/graph';
import * as Types from '@wandb/cg/browser/model/types';
import {registerPanel} from './PanelRegistry';
import * as Panel2 from './panel';
import {useNodeValue} from '@wandb/common/cgreact';
import * as ConfigPanel from './ConfigPanel';
import {callOp, toString} from '@wandb/cg/browser/hl';
import {Panel, PanelConfigEditor, Panel2Loader} from './PanelComp';
import {PanelContextProvider} from './PanelContext';

interface ServerOpDef {
  name: string;
  input_types: CGTypes.InputTypes;
  output_type: Types.Type;
  render_info: CGTypes.OpRenderInfo;
}

interface WeaveServerOpList {
  data: Array<ServerOpDef>;
}

interface UserPanelConfig {
  _renderAsPanel?: {
    panelId: string;
    panelConfig: any;
  };
}
type UserPanelProps = Panel2.PanelProps<'any', UserPanelConfig>;

const useUserPanelVars = (
  props: UserPanelProps,
  panelInputName: string,
  panelInputNodeType: Types.Type,
  renderOpName: string
) => {
  const {updateConfig} = props;
  const calledRender = useMemo(() => {
    const renderOpArgs = {
      [panelInputName]: {
        nodeType: 'const' as const,
        type: {
          type: 'function' as const,
          inputTypes: {},
          outputType: panelInputNodeType,
        },
        val: {
          nodeType: 'var' as const,
          type: panelInputNodeType,
          name: panelInputName,
        },
      },
    };
    return props.config?._renderAsPanel == null
      ? (callOp(renderOpName, renderOpArgs) as Types.Node)
      : Graph.voidNode();
  }, [panelInputName, panelInputNodeType, props.config, renderOpName]);
  const renderOpResult = useNodeValue(calledRender);
  const renderAsPanel = useMemo(
    () =>
      props.config?._renderAsPanel ??
      (renderOpResult.loading
        ? {panelId: '', panelConfig: undefined}
        : {
            panelId: renderOpResult.result.id,
            panelConfig: renderOpResult.result.config,
          }),
    [props.config, renderOpResult]
  );
  const updatePanelConfig = useCallback(
    (newPanelConfig: any) => {
      updateConfig({
        _renderAsPanel: {
          panelId: renderAsPanel.panelId,
          panelConfig: {...renderAsPanel.panelConfig, ...newPanelConfig},
        },
      });
    },
    [updateConfig, renderAsPanel.panelId, renderAsPanel.panelConfig]
  );
  return useMemo(
    () => ({
      renderAsPanel,
      updatePanelConfig,
      modified: props.config?._renderAsPanel != null,
      loading: calledRender.nodeType !== 'void' && renderOpResult.loading,
    }),
    [
      renderAsPanel,
      updatePanelConfig,
      props.config,
      calledRender.nodeType,
      renderOpResult.loading,
    ]
  );
};

const registerUserPanel = (op: ServerOpDef) => {
  const opInputName0 = Object.keys(op.input_types)[0];
  const opInputType0 = Object.values(op.input_types)[0];
  if (!Types.isFunction(opInputType0)) {
    console.warn('non-function type for panel op: ', op);
    return;
  }
  const inputType = opInputType0.outputType;

  console.log('Registering panel', op, inputType);

  const ConfigComponent: React.FC<UserPanelProps> = props => {
    const {renderAsPanel, updatePanelConfig, loading, modified} =
      useUserPanelVars(props, opInputName0, props.input.type, op.name);
    if (loading) {
      return <Panel2Loader />;
    }
    return (
      <>
        {modified && <div>* Unsaved changes *</div>}
        <ConfigPanel.ConfigOption label="Input">
          {opInputName0}: {toString(props.input)}
        </ConfigPanel.ConfigOption>
        <ConfigPanel.ConfigOption label="Panel">
          {renderAsPanel.panelId}
        </ConfigPanel.ConfigOption>
        <PanelConfigEditor
          panelSpec={renderAsPanel.panelId}
          input={Graph.voidNode()}
          config={renderAsPanel.panelConfig}
          updateConfig={updatePanelConfig}
        />
      </>
    );
  };
  const RenderComponent: React.FC<UserPanelProps> = props => {
    const {renderAsPanel, updatePanelConfig, loading} = useUserPanelVars(
      props,
      opInputName0,
      props.input.type,
      op.name
    );
    if (loading) {
      return <Panel2Loader />;
    }
    return (
      <PanelContextProvider newVars={{[opInputName0]: props.input}}>
        <Panel
          panelSpec={renderAsPanel.panelId}
          input={Graph.voidNode()}
          config={renderAsPanel.panelConfig}
          updateConfig={updatePanelConfig}
        />
      </PanelContextProvider>
    );
  };

  registerPanel({
    id: op.name,
    ConfigComponent,
    Component: RenderComponent,
    inputType: inputType,
  });
};

const serverOpIsPanel = (op: ServerOpDef) => {
  return !Types.isSimpleType(op.output_type) && op.output_type.type === 'panel';
};

export const loadWeaveObjects = () => {
  // eslint-disable-next-line wandb/no-unprefixed-urls
  return fetch(backendWeaveHost() + '/ops')
    .then(res => res.json())
    .then((opList: WeaveServerOpList) => {
      for (const op of opList.data) {
        let opExists = true;
        try {
          Graph.getOpDef(op.name);
        } catch {
          opExists = false;
        }

        if (opExists) {
          continue;
        }

        const argDescriptions: {[key: string]: string} = {};
        for (const arg of Object.keys(op.input_types)) {
          argDescriptions[arg] = 'none'; // TODO(DG): Replace this with an actual description of args
        }

        let isPanel = false;
        if (serverOpIsPanel(op)) {
          isPanel = true;
          registerUserPanel(op);
        }

        console.log(`MAKING OP: ${op.name}`, op.output_type);
        Graph.makeOp({
          name: op.name,
          hidden: isPanel,
          argTypes: op.input_types,
          returnType: op.output_type,
          description: op.name, // TODO(DG): replace with real description
          argDescriptions,
          returnValueDescription: op.name, // TODO(DG): replace with real description
          renderInfo: op.render_info,
        });
      }
    });
};
