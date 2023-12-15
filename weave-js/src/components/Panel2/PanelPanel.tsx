import {Client, constNodeUnsafe, NodeOrVoidNode} from '@wandb/weave/core';
import produce from 'immer';
import _ from 'lodash';
import React, {
  Dispatch,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
// Import from reinspect instead of react. This is the same as the react useReducer
// but it hooks us up to redux devtools.
import {useReducer} from 'reinspect';

import {useWeaveContext} from '../../context';
import {useScrollbarVisibility} from '../../core/util/scrollbar';
import * as CGReact from '../../react';
import {useMutation} from '../../react';
import {consoleLog} from '../../util';
import {Button} from '../Button';
import * as SidebarConfig from '../Sidebar/Config';
import {Outline, shouldDisablePanelDelete} from '../Sidebar/Outline';
import {OutlineItemPopupMenu} from '../Sidebar/OutlineItemPopupMenu';
import {
  CHILD_PANEL_DEFAULT_CONFIG,
  ChildPanel,
  ChildPanelConfig,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
  getFullChildPanel,
} from './ChildPanel';
import * as Panel2 from './panel';
import {Panel2Loader, useUpdateConfig2} from './PanelComp';
import {PanelContextProvider, usePanelContext} from './PanelContext';
import {fixChildData} from './PanelGroup';
import {
  useCloseDrawer,
  useSelectedPath,
  useSetInteractingPanel,
} from './PanelInteractContext';
import {PanelPanelContextProvider} from './PanelPanelContextProvider';
import {useSetPanelRenderedConfig} from './PanelRenderedConfigContext';
import {
  getConfigForPath,
  refineAllExpressions,
  refineForUpdate,
  updateExpressionVarNamesFromConfig,
  updateExpressionVarTypes,
} from './panelTree';
import {toWeaveType} from './toWeaveType';

const inputType = {type: 'Panel' as const};
type PanelPanelProps = Panel2.PanelProps<
  typeof inputType,
  {
    /**
     * Unique identifier for a PanelPanel. Required if multiple
     * PanelPanels are rendered in a single PanelRootContext.
     */
    documentId?: string;
  }
>;

// There is a single reducer, stored in a single global context.
interface PanelRootsState {
  // Each loaded panel root is stored under an id in panelRoots.
  panelRoots: {
    [id: string]: PanelRootState;
  };
  dispatch: React.Dispatch<ActionWithId>;
}

interface PanelRootState {
  client: Client;
  persist: (root: ChildPanelFullConfig) => void;
  root: ChildPanelFullConfig;
  inFlight: boolean;
  nextActions: ActionWithId[];
}
interface ActionInit {
  type: 'init';
  client: Client;
  persist: (root: ChildPanelFullConfig) => void;
  root: ChildPanelFullConfig;
}

interface ActionSetConfig {
  type: 'setConfig';
  newConfig: ChildPanelFullConfig;
}

interface ActionFinishUpdateConfig {
  type: 'finishUpdateConfig';
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
  | ActionUpdateConfig2
  | ActionFinishUpdateConfig;

type ActionWithId = Action & {id: string};

const doUpdate = async (
  dispatch: Dispatch<ActionWithId>,
  client: Client,
  id: string,
  priorConfig: any,
  newConfig: any
) => {
  const refined = await refineForUpdate(client, priorConfig, newConfig);
  dispatch({type: 'finishUpdateConfig', newConfig: refined, id});
};

const panelRootReducer = (
  state: PanelRootsState,
  action: ActionWithId
): PanelRootsState => {
  if (action.type === 'init') {
    return produce(state, draft => {
      draft.panelRoots[action.id] = {
        client: action.client,
        root: action.root,
        persist: action.persist,
        inFlight: false,
        nextActions: [],
      };
    });
  }
  const panelRoot = state.panelRoots[action.id];
  if (panelRoot == null) {
    throw new Error(
      'Must initialize with init action, before any other action'
    );
  }
  switch (action.type) {
    case 'setConfig':
      // Note: we don't persist here. This is used after our initial async refining
      // at load time. We don't want to persist until the user makes a change for now
      // as it causes extra churn. We could detect if anything meaningful changed
      // and only persist if so.
      return produce(state, draft => {
        const draftPanelRoot = draft.panelRoots[action.id];
        draftPanelRoot.root = action.newConfig;
        draftPanelRoot.inFlight = false;
      });

    // Both updateConfig actions trigger an async flow, where we may refine
    // some expressions. While this is happening, we queue up new update
    // actions instead of firing them immediately.

    // Note, this doesn't actually work! Why? Because panels we do not receive
    // delta updates from updateConfig calls, we receive the whole config. Since
    // we don't immediately update the config, if a user makes a second change
    // while one is in flight, the second completion will restore the first change.
    // Accept this more now until we switch to delta updates.
    case 'updateConfig':
      const renamedConfig = updateExpressionVarNamesFromConfig(
        panelRoot.root,
        action.newConfig
      );
      const newAction = {
        ...action,
        newConfig: renamedConfig,
      };
      if (state.panelRoots[newAction.id].inFlight) {
        return produce(state, draft => {
          draft.panelRoots[newAction.id].nextActions.push(newAction);
        });
      }
      doUpdate(
        state.dispatch,
        panelRoot.client,
        newAction.id,
        panelRoot.root,
        newAction.newConfig
      );
      return produce(state, draft => {
        const panelRootForId = draft.panelRoots[newAction.id];
        panelRootForId.inFlight = true;
        panelRootForId.root = newAction.newConfig;
      });
    case 'updateConfig2':
      if (panelRoot.inFlight) {
        return produce(state, draft => {
          draft.panelRoots[action.id].nextActions.push(action);
        });
      }
      const configChanges = action.change(panelRoot.root);
      const newConfig = produce(panelRoot.root, draft => {
        for (const key of Object.keys(configChanges)) {
          (draft as any)[key] = (configChanges as any)[key];
        }
      });
      doUpdate(
        state.dispatch,
        panelRoot.client,
        action.id,
        panelRoot.root,
        newConfig
      );
      return produce(state, draft => {
        const panelRootForId = draft.panelRoots[action.id];
        panelRootForId.inFlight = true;
        panelRootForId.root = newConfig;
      });
    // This is the end of the async update config flow. We set the new config
    // and dispatch the next queued action if there is one.
    case 'finishUpdateConfig':
      const nextActions = [...panelRoot.nextActions];
      if (nextActions.length > 0) {
        const nextAction = nextActions.splice(0, 1)[0];
        state.dispatch(nextAction);
      } else {
        panelRoot.persist(action.newConfig);
      }
      return produce(state, draft => {
        const draftPanelRoot = draft.panelRoots[action.id];
        draftPanelRoot.root = action.newConfig;
        draftPanelRoot.inFlight = false;
        draftPanelRoot.nextActions = nextActions;
      });
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

interface PanelRootContextState {
  state: PanelRootsState;
  dispatch: React.Dispatch<ActionWithId>;
}

const PanelRootContext = React.createContext<PanelRootContextState | null>(
  null
);
PanelRootContext.displayName = 'PanelRootContext';

export const PanelRootContextProvider: React.FC<{}> = props => {
  // We hack the dispatch function into the state so the reducer can call it.
  const rootState = {panelRoots: {}, dispatch: () => {}} as any;
  const [state, dispatch] = useReducer(
    panelRootReducer,
    rootState,
    () => rootState,
    'PanelRoots'
  );
  rootState.dispatch = (innerAction: ActionWithId) => {
    // Ensure this is async so it happens after the reducer runs!
    setTimeout(() => {
      dispatch(innerAction);
    }, 1);
  };
  return <PanelRootContext.Provider value={{state, dispatch}} {...props} />;
};

export function usePanelRootContext(id: string) {
  const ctx = useContext(PanelRootContext);
  if (ctx == null) {
    throw new Error(
      'usePanelRootContext must be used within a PanelRootContextProvider'
    );
  }
  const {state: rootState, dispatch: rootDispatch} = ctx;

  const state = rootState.panelRoots[id] ?? null;
  const dispatch = useCallback(
    (action: Action) => {
      rootDispatch({...action, id} as any);
    },
    [id, rootDispatch]
  );
  return {state, dispatch};
}

const usePanelPanelCommon = (props: PanelPanelProps) => {
  const weave = useWeaveContext();
  const selectedPanel = useSelectedPath();
  const setInteractingPanel = useSetInteractingPanel();
  // const panelConfig = props.config;

  // TODO: props.input is not the right default ID to use!!! The expression string changes when the panel
  // is renamed or published. Need to figure out how to get an ID shared across the Render
  // and Config components here... this probably something simple to do.
  // The path through the React tree... could work. Then panel path? Idk
  const documentId = props.config?.documentId ?? weave.expToString(props.input);

  const {state, dispatch} = usePanelRootContext(documentId);
  const initialLoading = state == null;
  const panelConfig = state?.root;

  // useTraceUpdate('panelQuery', {
  //   loading: panelQuery.loading,
  //   result: panelQuery.result,
  // });

  useSetPanelRenderedConfig(panelConfig);

  const panelUpdateConfig = useCallback(
    (newConfig: any) => {
      dispatch({type: 'updateConfig', newConfig});
    },
    [dispatch]
  );
  // TODO: Not yet handling refinement in panelUpdateConfig2
  const panelUpdateConfig2 = useCallback(
    (change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig) => {
      dispatch({type: 'updateConfig2', change});
    },
    [dispatch]
  );
  consoleLog('PANEL PANEL RENDER CONFIG', panelConfig);

  return {
    dispatch,
    loading: initialLoading,
    documentId,
    panelConfig,
    selectedPanel,
    setInteractingPanel,
    panelUpdateConfig,
    panelUpdateConfig2,
  };
};

export const PanelPanelConfig: React.FC<PanelPanelProps> = props => {
  const {
    loading,
    documentId,
    panelConfig,
    selectedPanel,
    setInteractingPanel,
    panelUpdateConfig,
    panelUpdateConfig2,
  } = usePanelPanelCommon(props);

  const closeDrawer = useCloseDrawer();
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
    setInteractingPanel('config', [''], documentId);
  }, [documentId, setInteractingPanel]);

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
                onClick={closeDrawer}
              />
            </SidebarConfig.HeaderTopRight>
          </SidebarConfig.HeaderTop>
        </SidebarConfig.Header>
        <SidebarConfig.Body>
          <Outline
            config={panelConfig}
            updateConfig={panelUpdateConfig}
            updateConfig2={panelUpdateConfig2}
            setSelected={path =>
              setInteractingPanel('config', path, documentId)
            }
            selected={selectedPanel}
          />
        </SidebarConfig.Body>
      </SidebarConfig.Container>
    );
  }

  return (
    <SidebarConfig.Container>
      <SidebarConfig.Header>
        <SidebarConfig.HeaderTop lessLeftPad>
          <Button
            variant="ghost"
            size="small"
            icon="back"
            onClick={goBackToOutline}>
            Outline
          </Button>
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
              data-testid="close-panel-panel-config"
              variant="ghost"
              size="small"
              onClick={closeDrawer}
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
  const {
    loading,
    documentId,
    panelConfig,
    panelUpdateConfig,
    panelUpdateConfig2,
    dispatch,
  } = usePanelPanelCommon(props);

  const weave = useWeaveContext();
  const updateConfig2 = useUpdateConfig2(props);
  const {stack} = usePanelContext();
  const setPanelConfig = updateConfig2;
  const loaded = useRef(false);
  const panelQuery = CGReact.useNodeValue(props.input);
  const {updateInput} = props;
  const updateServerPanel = useUpdateServerPanel(
    props.input,
    updateInput as any
  );

  useEffect(() => {
    if (!panelQuery.loading) {
      const doLoad = async () => {
        // Always ensure vars have correct types first. This is syncrhonoous.
        const loadedPanel = updateExpressionVarTypes(panelQuery.result, stack);

        // Immediately render the document
        dispatch({
          type: 'init',
          client: weave.client,
          root: loadedPanel,
          persist: (newRoot: ChildPanelFullConfig) =>
            updateServerPanel(newRoot),
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
    dispatch,
    panelQuery.loading,
    panelQuery.result,
    setPanelConfig,
    stack,
    updateServerPanel,
    weave,
  ]);

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
        documentId={documentId}
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
