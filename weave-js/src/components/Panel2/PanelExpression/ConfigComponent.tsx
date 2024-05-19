import Loader from '@wandb/weave/common/components/WandbLoader';
import React from 'react';
import {Icon, Popup} from 'semantic-ui-react';

import {Button} from '../../Button';
import {PanelStack} from '../availablePanels';
import {ConfigOption, ModifiedDropdownConfigField} from '../ConfigPanel';
import {PanelContext, UpdateContext} from '../panel';
import {PanelComp2} from '../PanelComp';
import {PanelExpressionState} from './hooks';
import {
  ConfigurationContent,
  ConfigurationContentControls,
  ConfigurationContentItem,
  ConfigurationContentItems,
  LockToggleButton,
} from './styles';

const isTablePanelHandler = (currHandler: PanelStack | undefined) => {
  return (
    currHandler?.id === 'table' ||
    (currHandler?.id === 'merge' && (currHandler as any)?.child?.id === 'table')
  );
};

export const ConfigComponent: React.FC<
  Pick<
    PanelExpressionState,
    | 'applyEditingConfig'
    | 'calledExpanded'
    | 'configurableNodeSettings'
    | 'curPanelName'
    | 'deleteTailPanelOps'
    | 'discardEditingConfig'
    | 'editingConfigIsModified'
    | 'editingPanelConfig'
    | 'expArgsAreModified'
    | 'exprAndPanelLocked'
    | 'getEjectPanelConfigUpdate'
    | 'handlePanelChange'
    | 'handler'
    | 'inputPath'
    | 'isLoading'
    | 'panelOptions'
    | 'setConfigOpen'
    | 'toggleExprLock'
    | 'updateConfig'
    | 'updateEditingPanelConfig'
    | 'updateEditingPanelConfig2'
    | 'updatePanelInput'
    | 'weavePlotEnabled'
  > & {
    context: PanelContext;
    updateContext: UpdateContext;
  }
> = ({
  applyEditingConfig,
  calledExpanded,
  configurableNodeSettings,
  context,
  curPanelName,
  deleteTailPanelOps,
  discardEditingConfig,
  editingConfigIsModified,
  editingPanelConfig,
  expArgsAreModified,
  exprAndPanelLocked,
  getEjectPanelConfigUpdate,
  handlePanelChange,
  handler,
  inputPath,
  isLoading,
  panelOptions,
  setConfigOpen,
  toggleExprLock,
  updateConfig,
  updateContext,
  updateEditingPanelConfig,
  updateEditingPanelConfig2,
  updatePanelInput,
  weavePlotEnabled,
}) => {
  return (
    <ConfigurationContent data-test="config-panel">
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'justify-start',
        }}>
        <div
          style={{
            textAlign: 'center',
            fontWeight: 'bold',
            paddingRight: '4px',
          }}>
          Query Panel Settings
        </div>
        <Popup
          content={
            exprAndPanelLocked ? 'Expression Frozen' : 'Freeze Expression'
          }
          inverted
          size="mini"
          position="top center"
          trigger={
            <LockToggleButton onClick={toggleExprLock}>
              <Icon
                size="small"
                name={'snowflake outline'}
                color={exprAndPanelLocked ? 'blue' : 'black'}
              />
            </LockToggleButton>
          }
        />
      </div>
      {exprAndPanelLocked || (
        <ConfigOption label="Render As">
          <ModifiedDropdownConfigField
            selection
            disabled={isLoading}
            scrolling
            item
            direction="left"
            options={panelOptions}
            text={curPanelName}
            selectOnBlur={false}
            onChange={handlePanelChange}
            data-test="panel-select"
          />
        </ConfigOption>
      )}
      <ConfigurationContentItems>
        {isLoading ? (
          <Loader name="confige-content-items" />
        ) : (
          <>
            <>
              {configurableNodeSettings.map(
                (
                  {node, panel, config: nodeConfig, updateEditingConfig},
                  ndx
                ) => {
                  return (
                    <ConfigurationContentItem key={ndx}>
                      <PanelComp2
                        input={node}
                        inputType={node.type}
                        loading={false}
                        panelSpec={panel as any}
                        configMode={true}
                        context={context}
                        config={nodeConfig}
                        updateConfig={updateEditingConfig}
                        updateContext={() => {}}
                      />
                    </ConfigurationContentItem>
                  );
                }
              )}
            </>
            <>
              {calledExpanded.nodeType !== 'void' &&
                handler != null &&
                handler?.ConfigComponent != null && (
                  <>
                    {handler.id === 'plot' && weavePlotEnabled && (
                      // Special case for table...
                      // Should make a generic config panel and remove this
                      <ConfigurationContentItem>
                        <fieldset style={{borderWidth: '1px'}}>
                          <legend>Table Query</legend>
                          <Button
                            variant="secondary"
                            data-test="edit-table-query-button"
                            onClick={() => {
                              deleteTailPanelOps({
                                panelId: 'table',
                              });
                            }}>
                            Edit table query
                          </Button>
                        </fieldset>
                      </ConfigurationContentItem>
                    )}
                    <ConfigurationContentItem>
                      {expArgsAreModified ? (
                        <span>
                          Please apply above changes before configuring the
                          panel.
                        </span>
                      ) : (
                        <PanelComp2
                          input={inputPath}
                          inputType={calledExpanded.type}
                          loading={false}
                          panelSpec={handler}
                          configMode={true}
                          context={context}
                          config={editingPanelConfig}
                          updateConfig={updateEditingPanelConfig}
                          updateConfig2={updateEditingPanelConfig2}
                          updateContext={updateContext}
                          updateInput={updatePanelInput}
                        />
                      )}
                    </ConfigurationContentItem>
                  </>
                )}
            </>
            <>
              {isTablePanelHandler(handler) && weavePlotEnabled && (
                // Special case for table... Should make a generic
                <ConfigurationContentItem>
                  <fieldset style={{borderWidth: '1px'}}>
                    <legend>Table Query</legend>
                    <Button
                      variant="secondary"
                      data-test="plot-table-query-button"
                      onClick={() => {
                        updateConfig({
                          ...getEjectPanelConfigUpdate(),
                          panelId: 'plot',
                        });
                      }}>
                      Plot table query
                    </Button>
                  </fieldset>
                </ConfigurationContentItem>
              )}
            </>
          </>
        )}
      </ConfigurationContentItems>
      <ConfigurationContentControls>
        <div>
          <Button
            size="large"
            variant="ghost"
            className="mr-12"
            data-test="cancel-panel-config"
            disabled={isLoading}
            onClick={() => {
              setConfigOpen(false);
              discardEditingConfig();
            }}>
            Cancel
          </Button>
          <Button
            size="large"
            data-test="ok-panel-config"
            disabled={!editingConfigIsModified || isLoading}
            onClick={() => {
              setConfigOpen(false);
              applyEditingConfig();
            }}>
            Apply
          </Button>
        </div>
      </ConfigurationContentControls>
    </ConfigurationContent>
  );
};
