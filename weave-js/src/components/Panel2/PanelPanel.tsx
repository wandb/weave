import {constNodeUnsafe, NodeOrVoidNode} from '@wandb/weave/core';
import {produce} from 'immer';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

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
import {getConfigForPath} from './panelTree';
import * as SidebarConfig from '../Sidebar/Config';
import {useScrollbarVisibility} from '../../core/util/scrollbar';
import {PanelPanelContextProvider} from './PanelPanelContextProvider';
import {Button} from '../Button';

const inputType = {type: 'Panel' as const};
type PanelPanelProps = Panel2.PanelProps<
  typeof inputType,
  ChildPanelFullConfig
>;

export const useUpdateConfigForPanelNode = (
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
  const panelConfig = props.config;
  const initialLoading = panelConfig == null;
  const {stack} = usePanelContext();

  const setPanelConfig = updateConfig2;

  useEffect(() => {
    if (initialLoading && !panelQuery.loading) {
      const doLoad = async () => {
        const loadedPanel = getFullChildPanel(panelQuery.result);

        // Hydration is not totally correct yet and results in invalid states.
        // Turning it off for now. This means the UI can be consistent in other
        // ways: panels which expect to always have a config may have undefined.
        // Python may mass us unitialized panels (panels that don't have
        // configs, or even just expressions). We walk through and initialize
        // them here to make sure our panel state is valid.
        // let hydratedPanel: ChildPanelFullConfig;
        // try {
        //   hydratedPanel = await mapPanels(
        //     loadedPanel,
        //     stack,
        //     async (panel: ChildPanelFullConfig, childStack: Stack) => {
        //       if (panel.config != null) {
        //         return panel;
        //       }
        //       const {id, config} = await initPanel(
        //         weave,
        //         panel.input_node,
        //         panel.id,
        //         undefined,
        //         childStack
        //       );
        //       return {...panel, id, config};
        //     }
        //   );
        // } catch (e) {
        //   console.error('Error hydrating panel', e);
        //   return;
        // }

        const hydratedPanel = loadedPanel;
        setPanelConfig(() => hydratedPanel);
      };
      doLoad();
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

  const updateConfigForPanelNode = useUpdateConfigForPanelNode(
    props.input,
    updateInput as any
  );

  const panelUpdateConfig = useCallback(
    (newConfig: any) => {
      consoleLog('PANEL PANEL CONFIG UPDATE', newConfig);
      consoleLog('PANEL PANEL CONFIG UPDATE TYPE', toWeaveType(newConfig));
      setPanelConfig(origConfig => ({...origConfig, ...newConfig}));
      // Uncomment to enable panel state saving
      updateConfigForPanelNode(newConfig);
    },
    [setPanelConfig, updateConfigForPanelNode]
  );
  const panelUpdateConfig2 = useCallback(
    (change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig) => {
      setPanelConfig((currentConfig: ChildPanelFullConfig) => {
        if (currentConfig == null) {
          throw new Error('Cannot update config before it is loaded');
        }
        const configChanges = change(currentConfig);
        const newConfig = produce(currentConfig, (draft: any) => {
          for (const key of Object.keys(configChanges)) {
            (draft as any)[key] = (configChanges as any)[key];
          }
        });
        consoleLog('PANEL PANEL CONFIG UPDATE2', newConfig);
        updateConfigForPanelNode(newConfig);
        return newConfig;
      });
    },
    [setPanelConfig, updateConfigForPanelNode]
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
