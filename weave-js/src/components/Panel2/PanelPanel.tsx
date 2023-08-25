import {Client, constNodeUnsafe, NodeOrVoidNode} from '@wandb/weave/core';
import React, {
  Dispatch,
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from 'react';

import _ from 'lodash';
import {useWeaveContext} from '../../context';
import * as CGReact from '../../react';
import {useMutation} from '../../react';
import {consoleLog} from '../../util';
import {Outline, shouldDisablePanelDelete} from '../Sidebar/Outline';
import {
  ChildPanel,
  ChildPanelConfig,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
  getFullChildPanel,
  CHILD_PANEL_DEFAULT_CONFIG,
} from './ChildPanel';
import * as Panel2 from './panel';
import {Panel2Loader, useUpdateConfig2} from './PanelComp';
import {PanelContextProvider, usePanelContext} from './PanelContext';
import {fixChildData} from './PanelGroup';
import {toWeaveType} from './toWeaveType';
import {
  useCloseEditor,
  useSelectedPath,
  useSetInspectingPanel,
} from './PanelInteractContext';
import {useSetPanelRenderedConfig} from './PanelRenderedConfigContext';
import {OutlineItemPopupMenu} from '../Sidebar/OutlineItemPopupMenu';
import {
  getConfigForPath,
  refineAllExpressions,
  refineForUpdate,
  updateExpressionVarTypes,
} from './panelTree';
import * as SidebarConfig from '../Sidebar/Config';
import {useScrollbarVisibility} from '../../core/util/scrollbar';
import {PanelPanelContextProvider} from './PanelPanelContextProvider';
import {Button} from '../Button';
import produce from 'immer';

const inputType = {type: 'Panel' as const};
type PanelPanelProps = Panel2.PanelProps<
  typeof inputType,
  ChildPanelFullConfig
>;

interface State {
  dispatch: React.Dispatch<Action>;
  client: Client;
  root: ChildPanelFullConfig;
}
interface ActionInit {
  type: 'init';
  dispatch: React.Dispatch<Action>;
  client: Client;
  root: ChildPanelFullConfig;
}

interface ActionSetConfig {
  type: 'setConfig';
  newConfig: ChildPanelFullConfig;
}

interface ActionUpdateConfig {
  type: 'updateConfig';
  newConfig: ChildPanelFullConfig;
}

interface ActionUpdateConfig2 {
  type: 'updateConfig2';
  change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig;
}

type Action =
  | ActionInit
  | ActionSetConfig
  | ActionUpdateConfig
  | ActionUpdateConfig2;

const doUpdate = async (
  dispatch: Dispatch<Action>,
  client: Client,
  priorConfig: any,
  newConfig: any
) => {
  const refined = await refineForUpdate(client, priorConfig, newConfig);
  dispatch({type: 'setConfig', newConfig: refined});
};

const panelRootReducer = (
  state: State | undefined,
  action: Action
): State | undefined => {
  if (action.type === 'init') {
    return {
      dispatch: action.dispatch,
      client: action.client,
      root: action.root,
    };
  }
  if (state == null) {
    throw new Error(
      'Must initialize with init action, before any other action.'
    );
  }
  switch (action.type) {
    case 'setConfig':
      return produce(state, draft => {
        draft.root = action.newConfig;
      });
    case 'updateConfig':
      doUpdate(state.dispatch, state.client, state.root, action.newConfig);

      return state;
    case 'updateConfig2':
      const configChanges = action.change(state.root);
      const newConfig = produce(state, draft => {
        for (const key of Object.keys(configChanges)) {
          (draft as any)[key] = (configChanges as any)[key];
        }
      });
      doUpdate(state.dispatch, state.client, state.root, newConfig);
      return state;
  }
  throw new Error('should not arrive here');
};

export const useUpdateServerPanel = (
  input: NodeOrVoidNode,
  updateInput?: (newInput: NodeOrVoidNode) => void
) => {
  const setServerPanelConfig = useMutation(input, 'set');

  const updateConfigForPanelNode = useCallback(
    (newConfig: any) => {
      // Need to do fixChildData because the panel config is not fully hydrated.
      const fixedConfig = fixChildData(getFullChildPanel(newConfig));
      setServerPanelConfig({
        val: constNodeUnsafe(toWeaveType(fixedConfig), fixedConfig),
      });
    },
    [setServerPanelConfig]
  );

  return updateConfigForPanelNode;
};

const usePanelPanelCommon = (props: PanelPanelProps) => {
  const weave = useWeaveContext();
  const {updateInput} = props;
  const updateConfig2 = useUpdateConfig2(props);
  const panelQuery = CGReact.useNodeValue(props.input);
  const selectedPanel = useSelectedPath();
  const setSelectedPanel = useSetInspectingPanel();
  // const panelConfig = props.config;
  const [state, dispatch] = useReducer(panelRootReducer, undefined);
  const initialLoading = state == null;
  const panelConfig = state?.root;
  const {stack} = usePanelContext();

  const setPanelConfig = updateConfig2;

  const loaded = useRef(false);

  const updateServerPanel = useUpdateServerPanel(
    props.input,
    updateInput as any
  );

  useEffect(() => {
    // Mirror results to the server.
    // We can put a debounce in here if this starts to seem bursty.
    if (panelConfig) {
      updateServerPanel(panelConfig);
    }
  }, [panelConfig, updateServerPanel]);

  useEffect(() => {
    if (initialLoading && !panelQuery.loading) {
      const doLoad = async () => {
        // Always ensure vars have correct types first. This is syncrhonoous.
        let loadedPanel = updateExpressionVarTypes(panelQuery.result, stack);

        // Immediately render the document
        dispatch({
          type: 'init',
          dispatch,
          client: weave.client,
          root: loadedPanel,
        });

        // Asynchronously refine all the expressions in the document.
        const refined = await refineAllExpressions(
          weave.client,
          loadedPanel,
          stack
        );

        // Set the newly refined document. This is usually a no-op,
        // unless:
        // - the document was not correctly refined already (
        //   e.g. if Python code is buggy and doesn't refine everything
        //   when constructing panels)
        // - the type of a data node changed, for example a new column
        //   was added to a table.
        // In the case where this does make changes, we may make some
        // new queries and rerender, causing a flash.
        //
        // TODO: store the newly refined state in the persisted document
        //   if there are changes, so that we don't have to do this again
        //   on reload.

        // Use the following logging to debug flashing and unexpected
        // post refinement changes.
        // console.log('ORIG', loadedPanel);
        // console.log('REFINED', refined);
        // console.log('DIFF', difference(loadedPanel, refined));
        dispatch({type: 'setConfig', newConfig: refined});
      };
      if (!loaded.current) {
        loaded.current = true;
        doLoad();
      }
      return;
    }
  }, [
    initialLoading,
    panelQuery.loading,
    panelQuery.result,
    setPanelConfig,
    stack,
    weave,
  ]);
  // useTraceUpdate('panelQuery', {
  //   loading: panelQuery.loading,
  //   result: panelQuery.result,
  // });

  useSetPanelRenderedConfig(panelConfig);

  const panelUpdateConfig = useCallback((newConfig: any) => {
    dispatch({type: 'updateConfig', newConfig});
  }, []);
  // TODO: Not yet handling refinement in panelUpdateConfig2
  const panelUpdateConfig2 = useCallback(
    (change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig) => {
      dispatch({type: 'updateConfig2', change});
    },
    []
  );
  consoleLog('PANEL PANEL RENDER CONFIG', panelConfig);

  return {
    loading: initialLoading,
    panelConfig,
    selectedPanel,
    setSelectedPanel,
    panelUpdateConfig,
    panelUpdateConfig2,
  };
};

export const PanelPanelConfig: React.FC<PanelPanelProps> = props => {
  const {
    loading,
    panelConfig,
    selectedPanel,
    setSelectedPanel,
    panelUpdateConfig,
    panelUpdateConfig2,
  } = usePanelPanelCommon(props);

  const closeEditor = useCloseEditor();
  const {
    visible: bodyScrollbarVisible,
    onScroll: onBodyScroll,
    onMouseMove: onBodyMouseMove,
  } = useScrollbarVisibility();

  const [isOutlineMenuOpen, setIsOutlineMenuOpen] = useState(false);
  const selectedIsRoot = useMemo(
    () => selectedPanel.filter(s => s).length === 0,
    [selectedPanel]
  );

  const localConfig = getConfigForPath(
    panelConfig || CHILD_PANEL_DEFAULT_CONFIG,
    selectedPanel
  );
  const shouldShowOutline = shouldDisablePanelDelete(
    localConfig,
    selectedPanel
  );

  const goBackToOutline = useCallback(() => {
    setSelectedPanel([``]);
  }, [setSelectedPanel]);

  if (loading) {
    return <Panel2Loader />;
  }
  if (panelConfig == null) {
    throw new Error('Panel config is null after loading');
  }

  // show outline instead of config panel if root, main, or varbar
  if (selectedIsRoot || shouldShowOutline) {
    return (
      <SidebarConfig.Container>
        <SidebarConfig.Header>
          <SidebarConfig.HeaderTop>
            <SidebarConfig.HeaderTopLeft>
              <SidebarConfig.HeaderTopText>Outline</SidebarConfig.HeaderTopText>
            </SidebarConfig.HeaderTopLeft>
            <SidebarConfig.HeaderTopRight>
              <Button
                icon="close"
                variant="ghost"
                size="small"
                onClick={closeEditor}
              />
            </SidebarConfig.HeaderTopRight>
          </SidebarConfig.HeaderTop>
        </SidebarConfig.Header>
        <Outline
          config={panelConfig}
          updateConfig={panelUpdateConfig}
          updateConfig2={panelUpdateConfig2}
          setSelected={setSelectedPanel}
          selected={selectedPanel}
        />
      </SidebarConfig.Container>
    );
  }

  return (
    <SidebarConfig.Container>
      <SidebarConfig.Header>
        <SidebarConfig.HeaderTop lessLeftPad>
          <SidebarConfig.HeaderTopLeft canGoBack onClick={goBackToOutline}>
            <Button icon="back" variant="ghost" size="small" />
            <SidebarConfig.HeaderTopText>Outline</SidebarConfig.HeaderTopText>
          </SidebarConfig.HeaderTopLeft>
          <SidebarConfig.HeaderTopRight>
            {!selectedIsRoot && !shouldShowOutline && (
              <OutlineItemPopupMenu
                config={panelConfig}
                localConfig={localConfig}
                path={selectedPanel}
                updateConfig={panelUpdateConfig}
                updateConfig2={panelUpdateConfig2}
                goBackToOutline={goBackToOutline}
                trigger={
                  <Button
                    icon="overflow-horizontal"
                    variant="ghost"
                    size="small"
                  />
                }
                isOpen={isOutlineMenuOpen}
                onOpen={() => setIsOutlineMenuOpen(true)}
                onClose={() => setIsOutlineMenuOpen(false)}
              />
            )}
            <Button
              icon="close"
              variant="ghost"
              size="small"
              onClick={closeEditor}
            />
          </SidebarConfig.HeaderTopRight>
        </SidebarConfig.HeaderTop>
        {!selectedIsRoot && (
          <SidebarConfig.HeaderTitle>
            {_.last(selectedPanel)}
          </SidebarConfig.HeaderTitle>
        )}
      </SidebarConfig.Header>
      <SidebarConfig.Body
        scrollbarVisible={bodyScrollbarVisible}
        onScroll={onBodyScroll}
        onMouseMove={onBodyMouseMove}>
        <PanelContextProvider newVars={{}} selectedPath={selectedPanel}>
          <ChildPanelConfigComp
            config={panelConfig}
            updateConfig={panelUpdateConfig}
            updateConfig2={panelUpdateConfig2}
          />
        </PanelContextProvider>
      </SidebarConfig.Body>
    </SidebarConfig.Container>
  );
};

export const PanelPanel: React.FC<PanelPanelProps> = props => {
  const {loading, panelConfig, panelUpdateConfig, panelUpdateConfig2} =
    usePanelPanelCommon(props);

  if (loading) {
    return <Panel2Loader />;
  }
  if (panelConfig == null) {
    throw new Error('Panel config is null after loading');
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'hidden',
        margin: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignContent: 'space-around',
        justifyContent: 'space-around',
      }}>
      <PanelPanelContextProvider
        config={panelConfig}
        updateConfig={panelUpdateConfig}
        updateConfig2={panelUpdateConfig2}>
        <ChildPanel
          config={panelConfig}
          updateConfig={panelUpdateConfig}
          updateConfig2={panelUpdateConfig2}
        />
      </PanelPanelContextProvider>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'panel',
  ConfigComponent: PanelPanelConfig,
  Component: PanelPanel,
  inputType,
};
