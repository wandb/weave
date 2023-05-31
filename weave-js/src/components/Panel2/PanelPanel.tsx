import * as globals from '@wandb/weave/common/css/globals.styles';
import {useTraceUpdate} from '@wandb/weave/common/util/hooks';
import {constNodeUnsafe, Node} from '@wandb/weave/core';
import produce from 'immer';
import React, {useCallback, useEffect, useMemo} from 'react';

import _ from 'lodash';
import styled, {css} from 'styled-components';
import {useWeaveContext} from '../../context';
import * as CGReact from '../../react';
import {useMutation} from '../../react';
import {consoleLog} from '../../util';
import {Outline} from '../Sidebar/Outline';
import {
  ChildPanel,
  ChildPanelConfig,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
  getFullChildPanel,
} from './ChildPanel';
import {
  IconBack as IconBackUnstyled,
  IconClose as IconCloseUnstyled,
  IconOverflowHorizontal as IconOverflowHorizontalUnstyled,
} from './Icons';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import {PanelContextProvider} from './PanelContext';
import {fixChildData, toWeaveType} from './PanelGroup';
import {
  useCloseEditor,
  useSelectedPath,
  useSetInspectingPanel,
} from './PanelInteractContext';
import {useSetPanelRenderedConfig} from './PanelRenderedConfigContext';
import {OutlineItemMenuPopup} from '../Sidebar/OutlineItemMenuPopup';
import {getConfigForPath} from './panelTree';

const inputType = {type: 'Panel' as const};
type PanelPanelProps = Panel2.PanelProps<
  typeof inputType,
  ChildPanelFullConfig
>;

const usePanelPanelCommon = (props: PanelPanelProps) => {
  const weave = useWeaveContext();
  const {updateConfig2, updateInput} = props;
  if (updateConfig2 == null) {
    throw new Error('updateConfig2 is required');
  }
  const panelQuery = CGReact.useNodeValue(props.input);
  const selectedPanel = useSelectedPath();
  const setSelectedPanel = useSetInspectingPanel();
  const panelConfig = props.config;
  const initialLoading = panelConfig == null;

  const setPanelConfig = updateConfig2;

  useEffect(() => {
    if (initialLoading && !panelQuery.loading) {
      setPanelConfig(() => getFullChildPanel(panelQuery.result));
      return;
    }
  }, [initialLoading, panelQuery.loading, panelQuery.result, setPanelConfig]);
  useTraceUpdate('panelQuery', {
    loading: panelQuery.loading,
    result: panelQuery.result,
  });

  useSetPanelRenderedConfig(panelConfig);

  const handleRootUpdate = useCallback(
    (newVal: Node) => {
      consoleLog('PANEL PANEL HANDLE ROOT UPDATE', newVal);
      if (
        weave.expToString(props.input) !== weave.expToString(newVal) &&
        updateInput
      ) {
        updateInput(newVal as any);
      }
    },
    [props.input, updateInput, weave]
  );

  const setServerPanelConfig = useMutation(
    props.input,
    'set',
    handleRootUpdate
  );

  const panelUpdateConfig = useCallback(
    (newConfig: any) => {
      consoleLog('PANEL PANEL CONFIG UPDATE', newConfig);
      consoleLog('PANEL PANEL CONFIG UPDATE TYPE', toWeaveType(newConfig));
      setPanelConfig(origConfig => ({...origConfig, ...newConfig}));
      // Uncomment to enable panel state saving
      // Need to do fixChildData because the panel config is not fully hydrated.
      const fixedConfig = fixChildData(getFullChildPanel(newConfig), weave);
      setServerPanelConfig({
        val: constNodeUnsafe(toWeaveType(fixedConfig), fixedConfig),
      });
    },
    [setPanelConfig, setServerPanelConfig, weave]
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
        // Need to do fixChildData because the panel config is not fully hydrated.
        const fixedConfig = fixChildData(getFullChildPanel(newConfig), weave);
        setServerPanelConfig({
          val: constNodeUnsafe(toWeaveType(fixedConfig), fixedConfig),
        });
        return newConfig;
      });
    },
    [setPanelConfig, setServerPanelConfig, weave]
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

  const showOutline = useMemo(
    () => selectedPanel.filter(s => s).length === 0,
    [selectedPanel]
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

  if (showOutline) {
    return (
      <Container>
        <Header>
          <HeaderTop>
            <HeaderTopLeft>
              <HeaderTopText>Outline</HeaderTopText>
            </HeaderTopLeft>
            <HeaderTopRight>
              <IconButton onClick={closeEditor}>
                <IconClose />
              </IconButton>
            </HeaderTopRight>
          </HeaderTop>
        </Header>
        <Outline
          config={panelConfig}
          updateConfig={panelUpdateConfig}
          updateConfig2={panelUpdateConfig2}
          setSelected={setSelectedPanel}
          selected={selectedPanel}
        />
      </Container>
    );
  }

  return (
    <Container>
      <Header>
        <HeaderTop lessLeftPad>
          <HeaderTopLeft canGoBack onClick={goBackToOutline}>
            <IconButton>
              <IconBack />
            </IconButton>
            <HeaderTopText>Outline</HeaderTopText>
          </HeaderTopLeft>
          <HeaderTopRight>
            <OutlineItemMenuPopup
              config={panelConfig}
              localConfig={getConfigForPath(panelConfig, selectedPanel)}
              path={selectedPanel}
              updateConfig={panelUpdateConfig}
              updateConfig2={panelUpdateConfig2}
              goBackToOutline={goBackToOutline}
              trigger={
                <IconButton>
                  <IconOverflowHorizontal />
                </IconButton>
              }
            />
            <IconButton onClick={closeEditor}>
              <IconClose />
            </IconButton>
          </HeaderTopRight>
        </HeaderTop>
        <HeaderTitle>{_.last(selectedPanel)}</HeaderTitle>
      </Header>
      <Body>
        <PanelContextProvider newVars={{}} selectedPath={selectedPanel}>
          <ChildPanelConfigComp
            config={panelConfig}
            updateConfig={panelUpdateConfig}
            updateConfig2={panelUpdateConfig2}
          />
        </PanelContextProvider>
      </Body>
    </Container>
  );
};

const IconButton = styled.div`
  width: 24px;
  height: 24px;
  cursor: pointer;
  display: flex;
  justify-content: center;
  align-items: center;

  color: ${globals.GRAY_500};
  &:hover {
    color: ${globals.GRAY_600};
    background-color: ${globals.GRAY_50};
  }

  &:not(:last-child) {
    margin-right: 4px;
  }
`;

const iconStyles = css`
  width: 18px;
`;
const IconBack = styled(IconBackUnstyled)`
  ${iconStyles}
`;
const IconClose = styled(IconCloseUnstyled)`
  ${iconStyles}
`;
const IconOverflowHorizontal = styled(IconOverflowHorizontalUnstyled)`
  ${iconStyles}
`;

const Container = styled.div`
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
`;

const Header = styled.div`
  padding: 16px 0;
  border-bottom: 1px solid ${globals.GRAY_350};
`;

const HeaderTop = styled.div<{lessLeftPad?: boolean}>`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 8px 0 ${p => (p.lessLeftPad ? 8 : 12)}px;
`;

const HeaderTopLeft = styled.div<{canGoBack?: boolean}>`
  display: flex;
  align-items: center;
  ${p =>
    p.canGoBack &&
    css`
      color: ${globals.GRAY_500};
      cursor: pointer;
    `}
`;

const HeaderTopRight = styled.div`
  display: flex;
  align-items: center;
`;

const HeaderTopText = styled.div`
  font-weight: 600;
`;

const HeaderTitle = styled.div`
  font-family: 'Inconsolata', monospace;
  font-size: 20px;
  font-weight: 600;
  margin-top: 16px;
  padding: 0 12px;
`;

const Body = styled.div`
  flex-grow: 1;
  overflow-x: hidden;
  overflow-y: auto;
`;

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
      <ChildPanel
        config={panelConfig}
        updateConfig={panelUpdateConfig}
        updateConfig2={panelUpdateConfig2}
      />
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'panel',
  ConfigComponent: PanelPanelConfig,
  Component: PanelPanel,
  inputType,
};
