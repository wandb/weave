import React from 'react';
import {Icon, Menu, Popup} from 'semantic-ui-react';
import {Editor} from 'slate';
import {ThemeProvider} from 'styled-components';

import {WeaveActionContextProvider} from '../../../actions';
import getConfig from '../../../config';
import {useWeaveContext, useWeaveFeaturesContext} from '../../../context';
import {focusEditor, WeaveExpression} from '../../../panel/WeaveExpression';
import Sidebar from '../../Sidebar/Sidebar';
import {themes} from '../Editor.styles';
import {Panel2Loader, PanelComp2} from '../PanelComp';
import {PanelContextProvider} from '../PanelContext';
import {ExpressionEditorActions} from './actions';
import type {PanelExpressionProps} from './common';
import {ConfigComponent} from './ConfigComponent';
import {usePanelExpressionState} from './hooks';
import * as S from './styles';

const PanelExpression: React.FC<PanelExpressionProps> = props => {
  const state = usePanelExpressionState(props);
  const {
    calledExpanded,
    configOpen,
    exprAndPanelLocked,
    handler,
    inputPath,
    isLoading,
    newVars,
    refinedExpression,
    renderPanelConfig,
    setConfigOpen,
    updateExp,
    updatePanelInput,
    updateRenderPanelConfig,
    updateRenderPanelConfig2,
  } = state;
  const weave = useWeaveContext();
  const enableFullScreen = useWeaveFeaturesContext().fullscreenMode;

  const {updateConfig} = props;
  const onMount = React.useCallback(
    (editor: Editor) => {
      if (state.config.autoFocus) {
        focusEditor(editor);
        updateConfig({autoFocus: false});
      }
    },
    [updateConfig, state.config.autoFocus]
  );

  const actions = React.useMemo(
    () => ExpressionEditorActions(weave, updateExp),
    [updateExp, weave]
  );

  const {urlPrefixed} = getConfig();

  return (
    <ThemeProvider theme={themes.light}>
      <S.Main>
        <S.EditorBar style={{pointerEvents: isLoading ? 'none' : 'auto'}}>
          {
            <div style={{width: '100%'}}>
              <Menu
                borderless
                style={{
                  border: 'none',
                  minHeight: '2rem',
                  marginBottom: '2px',
                  borderBottom: '1px solid lightgray',
                  borderRadius: '0px',
                  boxShadow: 'none',
                  padding: '5px',
                }}>
                <Menu.Menu style={{fontSize: '1rem', flex: '1 1 auto'}}>
                  <Menu.Item
                    style={{padding: 0, flex: '1 1 auto'}}
                    disabled={isLoading}>
                    {exprAndPanelLocked || (
                      <div
                        style={{width: '100%'}}
                        data-test="panel-expression-expression" // Note: make sure to update the onMouseEnter check in HoveringToolbar if this changes
                      >
                        <PanelContextProvider newVars={newVars}>
                          <WeaveExpression
                            expr={refinedExpression}
                            setExpression={updateExp}
                            noBox
                            onMount={onMount}
                          />
                        </PanelContextProvider>
                      </div>
                    )}
                  </Menu.Item>
                </Menu.Menu>
                <Menu.Menu position="right" style={{flex: '0 0 auto'}}>
                  {/* This URL won't work in W&B prod yet. Feature is only on for weave app currently */}
                  {enableFullScreen && (
                    <Menu.Item style={{padding: 0}}>
                      <S.BarButton
                        onClick={() => {
                          const expStr = weave
                            .expToString(refinedExpression)
                            .replace(/\n+/g, '')
                            .replace(/\s+/g, '');
                          window.open(
                            urlPrefixed(`?exp=${encodeURIComponent(expStr)}`),
                            '_blank'
                          );
                        }}>
                        <Icon name="external square alternate" />
                      </S.BarButton>
                    </Menu.Item>
                  )}
                  <Menu.Item style={{padding: 0}}>
                    {props.standalone ? (
                      <S.BarButton
                        disabled={isLoading}
                        data-test="panel-config"
                        onClick={() => setConfigOpen(!configOpen)}>
                        <Icon
                          name="cog"
                          style={{
                            color: configOpen ? '#2e78c7' : 'inherit',
                          }}
                        />
                      </S.BarButton>
                    ) : null}
                    {!props.standalone ? (
                      <Popup
                        basic
                        closeOnDocumentClick={false}
                        position="right center"
                        popperModifiers={{
                          preventOverflow: {
                            boundary: 'element',
                          },
                        }}
                        popperDependencies={[isLoading]}
                        trigger={
                          <div>
                            <S.ConfigButton
                              disabled={isLoading}
                              data-test="panel-config"
                              style={{
                                padding: '5px',
                              }}>
                              <Icon
                                name="cog"
                                style={{
                                  margin: 0,
                                  color: configOpen ? '#2e78c7' : 'inherit',
                                }}
                              />
                            </S.ConfigButton>
                          </div>
                        }
                        on="click"
                        open={configOpen}
                        onOpen={() => setConfigOpen(true)}
                        onClose={() => setConfigOpen(false)}>
                        <ConfigComponent
                          {...state}
                          context={props.context}
                          updateContext={props.updateContext}
                        />
                      </Popup>
                    ) : null}
                  </Menu.Item>
                </Menu.Menu>
              </Menu>
            </div>
          }
        </S.EditorBar>
        <S.PanelHandler>
          <S.PanelHandlerContent data-test="panel-expression-content">
            {isLoading ? (
              <Panel2Loader />
            ) : (
              calledExpanded.nodeType !== 'void' &&
              handler != null && (
                <WeaveActionContextProvider newActions={actions}>
                  <PanelComp2
                    input={inputPath}
                    inputType={calledExpanded.type}
                    loading={false}
                    panelSpec={handler}
                    configMode={false}
                    context={props.context}
                    config={renderPanelConfig}
                    updateConfig={updateRenderPanelConfig}
                    updateConfig2={updateRenderPanelConfig2}
                    updateContext={props.updateContext}
                    updateInput={updatePanelInput}
                    noPanelControls
                  />
                </WeaveActionContextProvider>
              )
            )}
          </S.PanelHandlerContent>
        </S.PanelHandler>
        {props.standalone ? (
          <S.SidebarWrapper>
            <Sidebar close={() => setConfigOpen(false)} collapsed={!configOpen}>
              {configOpen && (
                <ConfigComponent
                  {...state}
                  context={props.context}
                  updateContext={props.updateContext}
                />
              )}
            </Sidebar>
          </S.SidebarWrapper>
        ) : null}
      </S.Main>
    </ThemeProvider>
  );
};

export default PanelExpression;
