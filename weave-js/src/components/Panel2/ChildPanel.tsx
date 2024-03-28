// Critical performance note: We must not depend on config/updateConfig
// in the callbacks we construct here. The stack that we construct in PanelContext
// depends on the callbacks, and we don't want to depend on current config state.
// If we do depend on current config state, everything in the UI will re-render
// all the time, because everything depends on stack.

import EditableField from '@wandb/weave/common/components/EditableField';
import {
  GRAY_50,
  GRAY_350,
  linkHoverBlue,
  MOON_50,
} from '@wandb/weave/common/css/globals.styles';
import {ValidatingTextInput} from '@wandb/weave/components/ValidatingTextInput';
import {
  defaultLanguageBinding,
  filterNodes,
  Frame,
  ID,
  isAssignableTo,
  isNodeOrVoidNode,
  Node,
  NodeOrVoidNode,
  Stack,
  varNode,
  voidNode,
  Weave,
} from '@wandb/weave/core';
import {replaceChainRoot} from '@wandb/weave/core/mutate';
import {isValidVarName} from '@wandb/weave/core/util/var';
import * as _ from 'lodash';
import React, {
  RefObject,
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import styled from 'styled-components';

import {useWeaveContext} from '../../context';
import {WeaveExpression} from '../../panel/WeaveExpression';
import {consoleLog} from '../../util';
import {Button} from '../Button';
import {OutlineItemPopupMenu} from '../Sidebar/OutlineItemPopupMenu';
import {Tooltip} from '../Tooltip';
import {
  excludePanelPanel,
  getPanelStacksForType,
  panelSpecById,
  usePanelStacksForType,
} from './availablePanels';
import * as ConfigPanel from './ConfigPanel';
import {ConfigSection} from './ConfigPanel';
import {PanelInput, PanelProps} from './panel';
import {Panel, PanelConfigEditor, useUpdateConfig2} from './PanelComp';
import {
  ExpressionEvent,
  PanelContextProvider,
  usePanelContext,
} from './PanelContext';
import * as Styles from './PanelExpression/styles';
import {
  useCloseDrawer,
  usePanelInputExprIsHighlightedByPath,
  useSelectedDocumentId,
  useSelectedPath,
  useSetInteractingChildPanel,
  useSetInteractingPanel,
  useSetPanelInputExprIsHighlighted,
  useSetSelectedPanel,
} from './PanelInteractContext';
import {getStackIdAndName} from './panellib/libpanel';
import PanelNameEditor from './PanelNameEditor';
import {usePanelPanelContext} from './PanelPanelContextProvider';
import {TableState} from './PanelTable/tableState';
import {
  addChild,
  getConfigForPath,
  getPath,
  isInsideMain,
  isMain,
  nextPanelName,
} from './panelTree';
import {SelectPanelType} from './SelectPanelType';

// This could be rendered as a code block with assignments, like
// so.
// ```
// a = input + 4; // will be in scope of descendent panels
// return PanelWhatever(a / 2, panel_whatever_config)
// ```

const allowPanel = (stackId: string) => {
  return (
    stackId.includes('projection') ||
    stackId.includes('maybe') ||
    !stackId.includes('.')
  );
};

export interface ChildPanelFullConfig<C = any> {
  vars: Frame;
  input_node: NodeOrVoidNode;
  id: string;
  config: C;
}

export type ChildPanelConfig =
  | undefined
  | ChildPanelFullConfig
  | NodeOrVoidNode;

export const isChildPanelFullConfig = (o: any): o is ChildPanelFullConfig => {
  if (o != null && o.id != null && o.vars != null && o.input_node != null) {
    return true;
  }
  return false;
};

export const getFullChildPanel = (
  item: ChildPanelConfig
): ChildPanelFullConfig => {
  if (item == null) {
    return CHILD_PANEL_DEFAULT_CONFIG;
  } else if (isNodeOrVoidNode(item)) {
    return {...CHILD_PANEL_DEFAULT_CONFIG, input_node: item};
  } else {
    return item;
  }
};

const initPanelConfig = async (
  weave: Weave,
  id: string,
  // inputNode must be refined by caller
  inputNode: NodeOrVoidNode,
  stack: Stack
) => {
  const panelSpec = panelSpecById(id);
  if (panelSpec?.initialize != null) {
    return await panelSpec.initialize(weave, inputNode, stack);
  }
  return undefined;
};

export const initPanel = async (
  weave: Weave,
  inputNode: NodeOrVoidNode,
  panelId: string | undefined,
  allowedPanels: string[] | undefined,
  stack: Stack
): Promise<ChildPanelFullConfig> => {
  inputNode = await weave.refineNode(inputNode, stack);
  const {curPanelId: id} = getPanelStacksForType(inputNode.type, panelId, {
    allowedPanels,
    stackIdFilter: allowPanel,
    // Currently panelpanel cannot be nested within other child panels so we are excluding it here for now if nested
    excludePanelPanel: excludePanelPanel(stack),
  });
  if (id == null) {
    return {vars: {}, input_node: voidNode(), id: '', config: undefined};
  }
  return {
    vars: {},
    id,
    input_node: inputNode,
    config: await initPanelConfig(weave, id, inputNode, stack),
  };
};

export const mutateEnsureItemIsFullChildPanel = (
  // This first argument must be an immer Draft, but typescript blows
  // up if we annotate it.
  items: {[key: string]: ChildPanelConfig},
  key: string
): void => {
  const item = items[key];
  if (item == null) {
    items[key] = CHILD_PANEL_DEFAULT_CONFIG;
  } else if (isNodeOrVoidNode(item)) {
    items[key] = {...CHILD_PANEL_DEFAULT_CONFIG, input_node: item};
  }
};

export const childPanelFromTableState = (
  tableState: TableState,
  colId: string
): ChildPanelFullConfig => {
  return {
    vars: {},
    input_node: tableState.columnSelectFunctions[colId],
    id: tableState.columns[colId].panelId,
    config: tableState.columns[colId].panelConfig,
  };
};

export const CHILD_PANEL_DEFAULT_CONFIG: ChildPanelFullConfig = {
  vars: {},
  input_node: voidNode(),
  id: '',
  config: undefined,
};
export const useChildPanelConfig = (
  config: ChildPanelConfig
): ChildPanelFullConfig => {
  return useMemo(() => getFullChildPanel(config), [config]);
};

export interface ChildPanelProps {
  editable?: boolean;
  controlBar?: 'off' | 'editable' | 'titleBar';
  passthroughUpdate?: boolean;
  pathEl?: string;
  prefixButtons?: JSX.Element;
  allowedPanels?: string[];
  overflowVisible?: boolean;
  config: ChildPanelConfig | undefined;
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  updateConfig2?: (change: (oldConfig: any) => any) => void;
  updateInput?: (partialInput: PanelInput) => void;
  updateName?: (newName: string) => void;
}

// Create a plot panel from a table panel.
const insertPlotPanel = (
  panelPathTable: string[],
  updateConfig2: any,
  setInteractingPanel: any
) => {
  updateConfig2((oldConfig: any) => {
    oldConfig = getFullChildPanel(oldConfig);
    const tablePanel = getPath(oldConfig, panelPathTable);
    // We need to find the layout parameters for the panel being
    // duplicated inside its parent's grid config so we can insert
    // the clone next to the original and with the same width and height.
    const tableId = panelPathTable[panelPathTable.length - 1];
    const parentPath = panelPathTable.slice(0, -1);
    const parentPanel = getPath(oldConfig, parentPath);
    const parentLayouts = parentPanel.config.gridConfig.panels;
    const targetLayoutObject = _.find(parentLayouts, {
      id: tableId,
    });
    const duplicateLayout = targetLayoutObject?.layout;
    const plotPanelName = nextPanelName(Object.keys(parentPanel.config.items));
    const plotPanelPath = [...parentPath, plotPanelName];
    const plotPanel = {
      id: 'plot',
      input_node: tablePanel.input_node,
      config: undefined,
      vars: {},
    };
    const updatedConfig = addChild(
      oldConfig,
      parentPath,
      plotPanel,
      plotPanelName,
      duplicateLayout
    );
    setInteractingPanel('config', plotPanelPath, 'input');
    return updatedConfig;
  });
};

const useChildPanelCommon = (props: ChildPanelProps) => {
  const {updateConfig} = props;
  const updateConfig2 = useUpdateConfig2(props);
  const config = useChildPanelConfig(props.config);
  const {id: panelId, config: panelConfig} = config;
  const {input_node: panelInputExpr} = config;
  const weave = useWeaveContext();
  const {stack, path: parentPath} = usePanelContext();

  const {curPanelId, stackIds, handler} = usePanelStacksForType(
    panelInputExpr.type,
    panelId,
    {
      allowedPanels: props.allowedPanels,
      stackIdFilter: allowPanel,
      // Currently panelpanel cannot be nested within other child panels so we are excluding it here for now if nested
      excludePanelPanel: excludePanelPanel(stack),
    }
  );

  const panelOptions = useMemo(() => {
    return stackIds.map(si => {
      const isActive =
        handler != null &&
        si.displayName === getStackIdAndName(handler).displayName;
      return {
        text: si.displayName,
        value: si.id,
        key: si.id,
        active: isActive,
        selected: isActive,
        icon: si.icon,
        category: si.category,
      };
    });
  }, [handler, stackIds]);

  const curPanelName =
    handler != null ? getStackIdAndName(handler).displayName : '';

  const handlePanelChange = useCallback(
    async (newPanelId: string) => {
      const {id, config: newPanelConfig} = await initPanel(
        weave,
        config.input_node,
        newPanelId,
        props.allowedPanels,
        stack
      );
      updateConfig({...config, id, config: newPanelConfig});
    },
    [config, props.allowedPanels, stack, updateConfig, weave]
  );

  const initPanelForInput = useCallback(
    async (newExpression: NodeOrVoidNode) => {
      const {id, config: newPanelConfig} = await initPanel(
        weave,
        newExpression,
        undefined,
        props.allowedPanels,
        stack
      );
      updateConfig2(curConfig => ({
        ...curConfig,
        input_node: newExpression,
        id,
        config: newPanelConfig,
      }));
    },
    [props.allowedPanels, stack, updateConfig2, weave]
  );

  const updateExpression = useCallback(
    (newExpression: NodeOrVoidNode) => {
      if (weave.isExpLogicallyEqual(newExpression, panelInputExpr)) {
        // If expressions match, no update. This prevents glitching
        // when types change (which I think happens in panel composition
        // due to inconsistency between client and server detected types).
        // I don't think we have a case for updating just the type of
        // an expression at the moment, so I think this is safe.
        return;
      }

      if (
        handler?.inputType !== 'any' &&
        isAssignableTo(newExpression.type, handler?.inputType ?? 'invalid')
      ) {
        // If type didn't change, keep current settings
        updateConfig2(curConfig => ({...curConfig, input_node: newExpression}));
      } else if (curPanelId === 'Each') {
        // "stick" to each
        updateConfig2(curConfig => ({...curConfig, input_node: newExpression}));
      } else if (props.allowedPanels != null && curPanelId === 'Expression') {
        // Major hacks here. allowedPanels is currently only set in the sidebar,
        // so use that to detect if we're there.
        // Expression ends up being the default panel for new panels. So we "stick"
        // to Expression if we're in the sidebar.
        updateConfig2(curConfig => ({
          ...curConfig,
          input_node: newExpression,
          id: 'Expression',
          config: undefined,
        }));
      } else {
        // Auto panel behavior.
        initPanelForInput(newExpression);
      }
    },
    [
      weave,
      panelInputExpr,
      handler?.inputType,
      curPanelId,
      props.allowedPanels,
      updateConfig2,
      initPanelForInput,
    ]
  );

  let updatePanelInput: ((newInput: Node) => void) | undefined = useCallback(
    (newInput: Node) => {
      consoleLog('UPDATE PANEL INPUT', newInput);
      let newExp: Node;
      if (
        filterNodes(
          newInput,
          checkNode =>
            checkNode.nodeType === 'var' && checkNode.varName === 'input'
        ).length === 0
      ) {
        newExp = newInput;
      } else {
        newExp = weave.callFunction(newInput, {
          input: panelInputExpr,
        });
      }
      const doUpdate = async () => {
        try {
          const refined = await weave.refineNode(newExp, stack);
          updateExpression(refined);
        } catch (e) {
          return Promise.reject(e);
        }
        return Promise.resolve();
      };
      doUpdate().catch(e => {
        console.error('PanelExpression error', e);
        throw new Error(e);
      });
    },
    [panelInputExpr, weave, stack, updateExpression]
  );
  if (props.passthroughUpdate) {
    updatePanelInput = props.updateInput;
  }
  const updateAssignment = useCallback(
    (key: string, val: NodeOrVoidNode) => {
      updateConfig2(curConfig => ({
        ...curConfig,
        vars: {
          ...curConfig.vars,
          [key]: val,
        },
      }));
    },
    [updateConfig2]
  );

  const updatePanelConfig2 = useCallback(
    (change: <T>(oldConfig: T) => Partial<T>) => {
      if (updateConfig2 == null) {
        return;
      }
      updateConfig2(oldConfig => {
        oldConfig = getFullChildPanel(oldConfig);
        return {
          ...oldConfig,
          id: curPanelId ?? '',
          config: {...oldConfig.config, ...change(oldConfig.config)},
        };
      });
    },
    // Added depenedency on curPanelId which depends on current
    // config state :( which ruins updateConfig2
    // TODO: fix
    [updateConfig2, curPanelId]
  );

  const updatePanelConfig = useCallback(
    newPanelConfig =>
      updateConfig({
        ...config,
        id: curPanelId ?? '',
        config: {...config.config, ...newPanelConfig},
      }),

    [config, updateConfig, curPanelId]
  );

  const newVars = useMemo(
    () => ({...config.vars, input: panelInputExpr}),
    [config.vars, panelInputExpr]
  );

  // TODO: we shouldn't need this but pathEl is not always set currently.
  const path = useMemo(
    () =>
      props.pathEl != null ? parentPath.concat([props.pathEl]) : parentPath,
    [parentPath, props.pathEl]
  );

  const inputHighlighted = usePanelInputExprIsHighlightedByPath(path);

  const setPanelIsHighlightedByPath = useSetPanelInputExprIsHighlighted();
  const handleVarEvent = useCallback(
    (varName: string, target: NodeOrVoidNode, event: ExpressionEvent) => {
      consoleLog('CHILD PANEL HANDLE VAR EVENT', varName, target, event);
      if (varName === 'input') {
        if (event.id === 'hover') {
          setPanelIsHighlightedByPath(path, true);
        } else if (event.id === 'unhover') {
          setPanelIsHighlightedByPath(path, false);
        } else if (event.id === 'mutate') {
          updateExpression(replaceChainRoot(panelInputExpr, event.newRootNode));
        }
      } else {
        if (config.vars[varName] == null) {
          throw new Error(
            "Received var event for var we don't have " + varName
          );
        }
        if (event.id === 'mutate') {
          updateAssignment(
            varName,
            replaceChainRoot(config.vars[varName], event.newRootNode)
          );
        } else {
          consoleLog('ChildPanel Unhandled event for var', varName, event);
        }
      }
    },
    [
      config.vars,
      panelInputExpr,
      path,
      setPanelIsHighlightedByPath,
      updateAssignment,
      updateExpression,
    ]
  );
  const panelInput = useMemo(
    () => varNode(panelInputExpr.type, 'input'),
    [panelInputExpr.type]
  );

  const setInteractingPanel = useSetInteractingPanel();
  const setInteractingChildPanel = useSetInteractingChildPanel();

  return useMemo(
    () => ({
      curPanelId,
      handler,
      panelConfig,
      panelInputExpr,
      panelInput,
      stackIds,
      newVars,
      panelOptions,
      curPanelName,
      inputHighlighted,
      updateExpression,
      handlePanelChange,
      handleVarEvent,
      updatePanelConfig,
      updatePanelConfig2,
      updatePanelInput,
      setInteractingPanel,
      setInteractingChildPanel,
    }),
    [
      curPanelId,
      handler,
      panelConfig,
      panelInputExpr,
      panelInput,
      stackIds,
      newVars,
      panelOptions,
      curPanelName,
      inputHighlighted,
      updateExpression,
      handlePanelChange,
      handleVarEvent,
      updatePanelConfig,
      updatePanelConfig2,
      updatePanelInput,
      setInteractingPanel,
      setInteractingChildPanel,
    ]
  );
};

const varNameToTitle = (varName: string) => {
  return varName.replace(/_/g, ' ');
};

// This is the standard way to render subpanels. We should migrate
// other cases to this (Table cell, SelectPanel in Facet, and probably
// PanelExpression and PanelRootQuery)
export const ChildPanel: React.FC<ChildPanelProps> = props => {
  const {
    panelInput,
    panelConfig,
    handler,
    curPanelId,
    newVars,
    panelOptions,
    // inputHighlighted,
    panelInputExpr,
    handlePanelChange,
    handleVarEvent,
    updateExpression,
    updatePanelConfig,
    updatePanelConfig2,
    updatePanelInput,
    setInteractingPanel,
    setInteractingChildPanel,
  } = useChildPanelCommon(props);

  const {frame} = usePanelContext();
  const closeDrawer = useCloseDrawer();

  const validateName = useCallback(
    (newName: string) => {
      return isValidVarName(newName) && frame[newName] == null;
    },
    [frame]
  );

  const [isHoverPanel, setIsHoverPanel] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const [expressionFocused, setExpressionFocused] = useState(false);
  const onFocusExpression = useCallback(() => {
    setExpressionFocused(true);
  }, []);
  const onBlurExpression = useCallback(() => {
    setExpressionFocused(false);
  }, []);

  const {
    documentId,
    config: fullConfig,
    updateConfig,
    updateConfig2,
  } = usePanelPanelContext();
  const {path} = usePanelContext();
  const fullPath = [...path, props.pathEl ?? ''].filter(
    el => el != null && el !== ''
  );

  // Store the last mouse down coordinates so we can distinguish click from drag.
  const lastMouseDownCoordsRef = useRef({x: 0, y: 0});

  const selectedDocumentId = useSelectedDocumentId();
  const pathStr = useMemo(() => ['<root>', ...fullPath].join('.'), [fullPath]);
  const selectedPath = useSelectedPath();
  const selectedPathStr = useMemo(() => {
    if (selectedPath.length === 1 && selectedPath[0] === '') {
      return '<root>';
    }
    return ['<root>', ...selectedPath!].join('.');
  }, [selectedPath]);

  const isPanelSelected =
    selectedDocumentId === documentId &&
    selectedPathStr !== '<root>' &&
    selectedPathStr !== '<root>.main' &&
    (pathStr === selectedPathStr || isAncestor(pathStr, selectedPathStr));

  const {ref: editorBarRef, width: editorBarWidth} =
    useElementWidth<HTMLDivElement>();

  const controlBar = props.controlBar ?? 'off';

  const isVarNameEditable = props.editable || controlBar === 'editable';
  const setSelectedPanel = useSetSelectedPanel();
  const showEditControls = isPanelSelected || isHoverPanel;

  return curPanelId == null || handler == null ? (
    <div>
      No panel for type {defaultLanguageBinding.printType(panelInput.type)}
    </div>
  ) : (
    <Styles.Main
      data-weavepath={props.pathEl ?? 'root'}
      onMouseDown={event => {
        event.stopPropagation();
        lastMouseDownCoordsRef.current = {
          x: event.clientX,
          y: event.clientY,
        };
      }}
      onClick={event => {
        event.stopPropagation();
        if (isInsideMain(fullPath, 1)) {
          setSelectedPanel(fullPath);
        } else if (
          isMain(fullPath) &&
          event.clientX === lastMouseDownCoordsRef.current.x &&
          event.clientY === lastMouseDownCoordsRef.current.y
        ) {
          // User has clicked on the background of the main panel
          // and did not drag to a different position.
          // i.e. We don't change the selected panel if the user is dragging to resize a panel.
          setSelectedPanel(fullPath);
        }
      }}
      onMouseEnter={() => setIsHoverPanel(true)}
      onMouseLeave={() => setIsHoverPanel(false)}>
      {controlBar !== 'off' && (
        <Styles.EditorBar>
          <EditorBarContent className="edit-bar" ref={editorBarRef}>
            {(!isVarNameEditable || !showEditControls) &&
              props.pathEl != null && (
                <EditorBarTitleOnly>
                  {varNameToTitle(props.pathEl)}
                </EditorBarTitleOnly>
              )}
            <EditorBarHover show={isVarNameEditable && showEditControls}>
              {/* Variable name */}
              {props.pathEl != null && (
                <EditorPath>
                  <ValidatingTextInput
                    dataTest="panel-expression-path"
                    onCommit={props.updateName ?? (() => {})}
                    validateInput={validateName}
                    initialValue={props.pathEl}
                    maxWidth={
                      editorBarWidth != null ? editorBarWidth / 3 : undefined
                    }
                    maxLength={24}
                  />{' '}
                </EditorPath>
              )}
              {/* Panel picker */}
              {controlBar === 'editable' &&
                curPanelId !== 'Expression' &&
                curPanelId !== 'RootBrowser' && (
                  <PanelNameEditor
                    value={curPanelId ?? ''}
                    autocompleteOptions={panelOptions}
                    setValue={handlePanelChange}
                  />
                )}
              {/* Expression */}
              {controlBar === 'editable' ? (
                <EditorExpression data-test="panel-expression-expression">
                  <WeaveExpression
                    expr={panelInputExpr}
                    setExpression={updateExpression}
                    noBox
                    truncate={!expressionFocused}
                    onFocus={onFocusExpression}
                    onBlur={onBlurExpression}
                  />
                </EditorExpression>
              ) : (
                <div style={{width: '100%'}} />
              )}
            </EditorBarHover>
            {/* Control buttons */}
            {props.editable && (
              <EditorIcons visible={showEditControls || isMenuOpen}>
                {props.prefixButtons}
                {curPanelId === 'table' && (
                  <Button
                    variant="ghost"
                    size="small"
                    icon="chart-scatterplot"
                    tooltip="Create a plot from this table"
                    onClick={(ev: React.MouseEvent) => {
                      ev.stopPropagation();
                      insertPlotPanel(
                        fullPath,
                        updateConfig2,
                        setInteractingPanel
                      );
                    }}
                  />
                )}
                <Tooltip
                  position="top center"
                  trigger={
                    <Button
                      variant="ghost"
                      size="small"
                      icon="pencil-edit"
                      data-testid="open-panel-editor"
                      onClick={() =>
                        setInteractingChildPanel(
                          'config',
                          props.pathEl ?? '',
                          documentId
                        )
                      }
                    />
                  }>
                  Open panel editor
                </Tooltip>
                <OutlineItemPopupMenu
                  config={fullConfig}
                  localConfig={getConfigForPath(fullConfig, fullPath)}
                  path={fullPath}
                  updateConfig={updateConfig}
                  updateConfig2={updateConfig2}
                  trigger={
                    <Button
                      variant="ghost"
                      size="small"
                      icon="overflow-horizontal"
                    />
                  }
                  onOpen={() => setIsMenuOpen(true)}
                  onClose={() => setIsMenuOpen(false)}
                  isOpen={isMenuOpen}
                  goBackToOutline={closeDrawer}
                />
              </EditorIcons>
            )}
          </EditorBarContent>
        </Styles.EditorBar>
      )}
      <PanelContainer overflowVisible={props.overflowVisible}>
        <PanelContextProvider
          newVars={newVars}
          handleVarEvent={handleVarEvent}
          newPath={props.pathEl}>
          {props.controlBar === 'titleBar' && curPanelId === 'Expression' ? (
            <div
              style={{
                margin: '0 16px',
                backgroundColor: MOON_50,
                padding: '4px 8px',
                borderRadius: '4px',
              }}>
              <WeaveExpression
                expr={panelInputExpr}
                setExpression={updateExpression}
                noBox
                truncate={!expressionFocused}
                onFocus={onFocusExpression}
                onBlur={onBlurExpression}
              />
            </div>
          ) : (
            <Panel
              input={panelInput}
              panelSpec={handler}
              config={panelConfig}
              updateConfig={updatePanelConfig}
              updateConfig2={updatePanelConfig2}
              updateInput={updatePanelInput}
            />
          )}
        </PanelContextProvider>
      </PanelContainer>
    </Styles.Main>
  );
};

const NEW_INSPECTOR_IMPLEMENTED_FOR = new Set([
  `plot`,
  `histogram`,
  `row`,
  `Group`,
  `Each`,
  `EachColumn`,
  `Facet`,
  `FacetTabs`,
  `LabeledItem`,
  `Sections`,
]);

// Return true if the panel with path maybeAncestorPath is an ancestor of the
// given panel's path. Returns false for self and other non-ancestors.
const isAncestor = (panelPath: string, maybeAncestorPath: string): boolean => {
  return panelPath.startsWith(maybeAncestorPath + '.');
};

export const ChildPanelConfigComp: React.FC<ChildPanelProps> = props => {
  const {
    newVars,
    panelInputExpr,
    panelInput,
    panelConfig,
    handler,
    curPanelId,
    panelOptions,
    handleVarEvent,
    handlePanelChange,
    updateExpression,
    updatePanelConfig,
    updatePanelConfig2,
    updatePanelInput,
  } = useChildPanelCommon(props);
  const config = useMemo(() => getFullChildPanel(props.config), [props.config]);

  const selectedPath = useSelectedPath();
  const {path} = usePanelContext();

  const pathStr = useMemo(() => {
    const fullPath = ['<root>', ...path, props.pathEl].filter(el => el != null);
    return fullPath.join('.');
  }, [path, props.pathEl]);
  const selectedPathStr = useMemo(() => {
    consoleLog(`selectedPath = ${JSON.stringify(selectedPath)}`);
    if (selectedPath.length === 1 && selectedPath[0] === '') {
      return '<root>';
    }
    return ['<root>', ...selectedPath!].join('.');
  }, [selectedPath]);

  // consoleLog(`selectedPath`, selectedPath, selectedPathStr);

  // Render everything along this path, and its descendants, but only show
  // the controls for this and its descendants.

  // Panels are organized into a tree as seen in the Outline. A board with a
  // variable and two panels in the main section might look like this:
  //
  // <root>
  //   sidebar
  //     data
  //   main
  //     panel
  //     panel0
  //
  // pathStr is a period-delimited string that identifies a panel.
  // E.g. <root>.main.panel0
  // The full delimited path is important for identification as e.g. "panel0" could
  // have a child that is also named "panel0".
  // We need to proceed with config display in three cases:
  // 1. This component is the selected component.
  // 2. This component is a descendent of the selected component. (E.g. parent is a Group)
  // 3. This component is an ancestor of the selected component, we need to recurse down.
  // For other cases display nothing.
  const isThisPanelSelected = pathStr === selectedPathStr;

  // Handle this panel is <root>.main.panel.child and <root>.main.panel is selected
  const isThisPanelDescendantOfSelected = isAncestor(pathStr, selectedPathStr);

  // Handle <root>.main.panel is selected and this is <root>.main
  const isThisPanelAncestorOfSelected = isAncestor(selectedPathStr, pathStr);

  const nothingToShow =
    !isThisPanelSelected &&
    !isThisPanelDescendantOfSelected &&
    !isThisPanelAncestorOfSelected;
  if (nothingToShow) {
    return null;
  }

  // If we are selected, expose controls for input expression, panel selection,
  // our config, and misc operations
  // If child is selected, render our config only
  // HAX: config component must check path for itself and passthrough
  //      as needed, for now
  const curPanelSelected =
    pathStr !== '<root>' && pathStr.startsWith(selectedPathStr);

  const dashboardConfigOptions = curPanelSelected ? (
    <>
      {curPanelId !== 'Group' && (
        <ConfigPanel.ConfigOption label="Input" multiline>
          <PanelContextProvider
            newVars={config.vars}
            handleVarEvent={handleVarEvent}>
            <ConfigPanel.ExpressionConfigField
              expr={panelInputExpr}
              setExpression={updateExpression}
            />
          </PanelContextProvider>
        </ConfigPanel.ConfigOption>
      )}
      <ConfigPanel.ConfigOption label="Panel type">
        <SelectPanelType
          value={curPanelId}
          options={panelOptions}
          onChange={({value}) => {
            if (typeof value === `string` && value) {
              handlePanelChange(value);
            }
          }}
        />
      </ConfigPanel.ConfigOption>

      <VariableEditor config={config} updateConfig={updatePanelConfig} />
    </>
  ) : null;

  if (curPanelId == null || handler == null) {
    return (
      <>
        {dashboardConfigOptions}
        <div>
          No panel for type {defaultLanguageBinding.printType(panelInput.type)}
        </div>
      </>
    );
  }

  return (
    <>
      {!NEW_INSPECTOR_IMPLEMENTED_FOR.has(handler.id) &&
        dashboardConfigOptions != null && (
          <ConfigSection label={`Properties`}>
            {dashboardConfigOptions}
          </ConfigSection>
        )}
      <PanelContextProvider
        newVars={newVars}
        newPath={props.pathEl}
        handleVarEvent={handleVarEvent}
        dashboardConfigOptions={dashboardConfigOptions}>
        <PanelConfigEditor
          input={panelInput}
          panelSpec={handler}
          config={panelConfig}
          updateConfig={updatePanelConfig}
          updateConfig2={updatePanelConfig2}
          updateInput={curPanelSelected ? props.updateInput : updatePanelInput}
        />
      </PanelContextProvider>
    </>
  );
};

const nextVarName = (vars: {[key: string]: any}) => {
  for (let i = 0; i < 26; i++) {
    const chr = String.fromCharCode(97 + i);
    if (vars[chr] == null) {
      return chr;
    }
  }
  return ID();
};

const MinimalEditableField = styled(EditableField)`
  margin: 0;
`;
MinimalEditableField.displayName = 'S.MinimalEditableField';

export const VariableEditor: React.FC<{
  config: ChildPanelFullConfig;
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
}> = ({config, updateConfig}) => {
  const frame: {[key: string]: NodeOrVoidNode} = {};
  const nextFrame = {...frame};
  if (_.isEmpty(config.vars)) {
    return null;
  }
  return (
    <ConfigPanel.ConfigOption label="variables">
      <div>
        {_.map(config.vars, (value, key) => {
          const varEditor = (
            <div key={key} style={{display: 'flex', alignItems: 'center'}}>
              <MinimalEditableField
                value={key}
                placeholder="var"
                save={newVarName => {
                  const newVars: {[key: string]: any} = {};
                  for (const [k, v] of Object.entries(config.vars)) {
                    if (k === key) {
                      newVars[newVarName] = v;
                    } else {
                      newVars[k] = v;
                    }
                  }
                  updateConfig({...config, vars: newVars});
                }}
              />
              <div style={{marginRight: 4, marginLeft: 4}}>= </div>
              <div style={{flexGrow: 1}}>
                <PanelContextProvider newVars={{...nextFrame}}>
                  <WeaveExpression
                    expr={value}
                    noBox
                    // liveUpdate
                    setExpression={val =>
                      updateConfig({
                        ...config,
                        vars: {...config.vars, [key]: val},
                      })
                    }
                  />
                </PanelContextProvider>
              </div>
            </div>
          );
          nextFrame[key] = value;
          return varEditor;
        })}
        <div
          style={{cursor: 'pointer', color: linkHoverBlue}}
          onClick={() =>
            updateConfig({
              ...config,
              vars: {
                ...config.vars,
                [nextVarName(config.vars)]: voidNode(),
              },
            })
          }>
          {/* + New variable */}
        </div>
      </div>
    </ConfigPanel.ConfigOption>
  );
};

export const VariableView: React.FC<{
  newVars: {[key: string]: NodeOrVoidNode};
}> = ({newVars}) => {
  const frame = newVars;
  const weave = useWeaveContext();
  return (
    <>
      {_.map(frame, (value, key) => (
        <ConfigPanel.ConfigOption key={key} label={_.capitalize(key)}>
          {weave.expToString(value)}
        </ConfigPanel.ConfigOption>
      ))}
    </>
  );
};

export const useChildPanelProps = (
  props: PanelProps<any, any>,
  configKey: string
) => {
  const {config, updateConfig2: parentUpdateConfig2} = props;
  if (config == null) {
    throw new Error('null config invalid for child panel');
  }
  if (parentUpdateConfig2 == null) {
    throw new Error('null updateConfig2 invalid for child panel');
  }
  const updateConfig = useCallback(
    newItemConfig =>
      parentUpdateConfig2(oldConfig => {
        console.log('1. NEW ITEM CONFIG', newItemConfig);
        return {
          ...oldConfig,
          [configKey]: newItemConfig, // Don't splat with ...config.item! ChildPanel always sends full config, and sometimes restructures its shape
        };
      }),

    [parentUpdateConfig2, configKey]
  );
  const updateConfig2 = useCallback(
    (change: (oldItemConfig: any) => any) => {
      parentUpdateConfig2(oldConfig => {
        const newItemConfig = change(oldConfig[configKey]);
        console.log('NEW ITEM CONFIG', newItemConfig);
        return {
          ...oldConfig,
          panel: newItemConfig, // Don't splat with ...config.item! ChildPanel always sends full config, and sometimes restructures its shape
        };
      });
    },
    [parentUpdateConfig2, configKey]
  );

  return {
    pathEl: configKey,
    config: config[configKey],
    updateConfig,
    updateConfig2,
  };
};

const EditorBarContent = styled.div`
  width: calc(100% + 16px);
  flex-shrink: 0;
  position: relative;
  left: -8px;
  padding: 2px 16px 8px;
  border-bottom: 1px solid ${GRAY_350};
  line-height: 20px;
  display: flex;
`;
EditorBarContent.displayName = 'S.EditorBarContent';

const EditorBarTitleOnly = styled.div`
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
  padding-left: 2px;
  flex-grow: 1;
`;
EditorBarTitleOnly.displayName = 'S.EditorBarTitleOnly';

// If the mouse leaves the panel we want to keep these contents (e.g. unsubmitted
// expression editor state) but just hide them.
const EditorBarHover = styled.div<{show: boolean}>`
  display: ${props => (props.show ? 'flex' : 'none')};
  align-items: flex-start;
  flex-grow: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
`;
EditorBarHover.displayName = 'S.EditorBarHover';

const EditorPath = styled.div`
  white-space: nowrap;
  margin-right: 8px;

  input {
    :focus {
      outline: none;
    }
    font-family: inherit;
  }
`;
EditorPath.displayName = 'S.EditorPath';

const EditorExpression = styled.div`
  flex-grow: 1;
  margin-left: 4px;
  overflow: hidden;
  &:hover {
    background-color: ${GRAY_50};
  }
`;
EditorExpression.displayName = 'S.EditorExpression';

const EditorIcons = styled.div<{visible: boolean}>`
  height: 20px;
  display: flex;
  align-items: center;
  margin-left: 8px;
  visibility: ${p => (p.visible ? `visible` : `hidden`)};
`;
EditorIcons.displayName = 'S.EditorIcons';

const PanelContainer = styled.div<{overflowVisible?: boolean}>`
  flex-grow: 1;
  overflow-y: ${p => (p.overflowVisible ? 'visible' : 'auto')};
`;
PanelContainer.displayName = 'S.PanelContainer';

type ElementWidth<T> = {
  ref: RefObject<T>;
  width: number | null;
};

function useElementWidth<T extends HTMLElement>(): ElementWidth<T> {
  const [elementWidth, setElementWidth] = useState<number | null>(null);
  const elementRef = useRef<T>(null);

  useLayoutEffect(() => {
    if (elementRef.current == null) {
      return;
    }

    const resizeObserver = new ResizeObserver(entries => {
      const entry = entries[0];
      if (entry == null) {
        return;
      }
      const w = entry.contentBoxSize[0].inlineSize;
      setElementWidth(w);
    });

    resizeObserver.observe(elementRef.current);

    return () => resizeObserver.disconnect();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elementRef.current]);

  return {ref: elementRef, width: elementWidth};
}
