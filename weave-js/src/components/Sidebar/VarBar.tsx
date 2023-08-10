import {NodeOrVoidNode} from '@wandb/weave/core';
import {produce} from 'immer';
import _ from 'lodash';
import React, {FC, memo, ReactNode, useCallback, useMemo} from 'react';
import {StrictMenuItemProps} from 'semantic-ui-react';
import styled from 'styled-components';
import {GRAY_350} from '../../common/css/globals.styles';
import {useWeaveContext} from '../../context';
import {useNodeWithServerType} from '../../react';
import {
  ChildPanelConfig,
  ChildPanelFullConfig,
  useChildPanelConfig,
} from '../Panel2/ChildPanel';
import * as ConfigPanel from '../Panel2/ConfigPanel';
import {IconDelete} from '../Panel2/Icons';
import {
  ExpressionEvent,
  PanelContextProvider,
  StackWithHandlers,
} from '../Panel2/PanelContext';
import {getItemVars, PanelGroupConfig} from '../Panel2/PanelGroup';
import {useSetInspectingChildPanel} from '../Panel2/PanelInteractContext';
import {Tooltip} from '../Tooltip';
import * as SidebarConfig from './Config';
import {PopupMenu} from './PopupMenu';
import {Button} from '../Button';

type VarBarProps = {
  config: PanelGroupConfig;
  updateConfig: (newConfig: PanelGroupConfig) => void;
  handleSiblingVarEvent: (
    varName: string,
    target: NodeOrVoidNode,
    event: ExpressionEvent
  ) => void;
  stack: StackWithHandlers;
  handleAddVar: () => void;
};

const VarBarComp: FC<VarBarProps> = props => {
  const {config, handleAddVar} = props;
  const numVars = Object.keys(config.items).length;
  const showEmptyState = numVars === 0;

  return (
    <VarBarContainer>
      <SidebarConfig.Container>
        <SidebarConfig.Header>
          <SidebarConfig.HeaderTop>
            <SidebarConfig.HeaderTopLeft>
              <SidebarConfig.HeaderTopText>
                Variables ({numVars})
              </SidebarConfig.HeaderTopText>
            </SidebarConfig.HeaderTopLeft>
            <SidebarConfig.HeaderTopRight>
              <Tooltip
                position="top center"
                trigger={<Button icon="add-new" onClick={handleAddVar} />}>
                New variable
              </Tooltip>
            </SidebarConfig.HeaderTopRight>
          </SidebarConfig.HeaderTop>
        </SidebarConfig.Header>
        {showEmptyState ? (
          <EmptyState />
        ) : (
          <SidebarConfig.Body>
            <ConfigPanel.ConfigSection>
              <Vars {...props} />
            </ConfigPanel.ConfigSection>
          </SidebarConfig.Body>
        )}
      </SidebarConfig.Container>
    </VarBarContainer>
  );
};

export const VarBar = memo(VarBarComp);

type VarsProps = VarBarProps;

const VarsComp: FC<VarsProps> = ({
  config,
  updateConfig,
  handleSiblingVarEvent,
  stack,
}) => {
  // HAX: Duplicated from PanelGroup.tsx
  const varChildren = useMemo(() => {
    let siblingVars: {[name: string]: NodeOrVoidNode} = {};
    const children: ReactNode[] = [];

    _.forEach(config.items, (item, name) => {
      const itemUpdateConfig = (newItemConfig: ChildPanelFullConfig) =>
        updateConfig(
          produce(config, draft => {
            draft.items[name] = newItemConfig;
          })
        );
      const deleteItem = () =>
        updateConfig(
          produce(config, draft => {
            delete draft.items[name];
          })
        );
      children.push(
        <Var
          key={name}
          name={name}
          config={item}
          updateConfig={itemUpdateConfig}
          deleteItem={deleteItem}
          siblingVars={siblingVars}
          handleSiblingVarEvent={handleSiblingVarEvent}
        />
      );
      siblingVars = {
        ...siblingVars,
        ...getItemVars(name, item, stack, config.allowedPanels),
      };
    });

    return children;
  }, [config, stack, updateConfig, handleSiblingVarEvent]);

  return <>{varChildren}</>;
};

const Vars = memo(VarsComp);

type VarProps = Pick<VarsProps, `handleSiblingVarEvent`> & {
  name: string;
  config: ChildPanelConfig;
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  deleteItem: () => void;
  siblingVars: {[name: string]: NodeOrVoidNode};
};

const VarComp: FC<VarProps> = ({
  name,
  config,
  updateConfig,
  deleteItem,
  siblingVars,
  handleSiblingVarEvent,
}) => {
  const weave = useWeaveContext();
  const setInspectingPanel = useSetInspectingChildPanel();

  const childPanelConfig = useChildPanelConfig(config);
  const panelInputExpr = useNodeWithServerType(
    childPanelConfig.input_node
  ).result;

  // HAX: Duplicated from ChildPanel.tsx
  const updateExpression = useCallback(
    (newExpression: NodeOrVoidNode) => {
      if (
        weave.expToString(newExpression) ===
        weave.expToString(childPanelConfig.input_node)
      ) {
        // If expression strings match, no update. This prevents glitching
        // when types change (which I think happens in panel composition
        // due to inconsistency between client and server detected types).
        // I don't think we have a case for updating just the type of
        // an expression at the moment, so I think this is safe.
        return;
      }

      updateConfig({
        ...childPanelConfig,
        input_node: newExpression,
        id: 'Expression',
        config: undefined,
      });
    },
    [weave, childPanelConfig, updateConfig]
  );

  const menuItems: StrictMenuItemProps[] = useMemo(
    () => [
      {
        key: 'delete',
        content: 'Delete',
        icon: <IconDelete />,
        onClick: deleteItem,
      },
    ],
    [deleteItem]
  );

  return (
    <ConfigPanel.ConfigOption
      label={name}
      multiline
      actions={
        <>
          <Tooltip
            position="top center"
            trigger={
              <Button
                icon="pencil-edit"
                onClick={() => setInspectingPanel(name)}
              />
            }>
            Open panel editor
          </Tooltip>
          <PopupMenu
            trigger={
              <Button variant="ghost" size="small" icon="overflow-horizontal" />
            }
            position={`bottom right`}
            items={menuItems}
          />
        </>
      }>
      <PanelContextProvider
        newVars={siblingVars}
        handleVarEvent={handleSiblingVarEvent}>
        <ConfigPanel.ExpressionConfigField
          expr={panelInputExpr}
          setExpression={updateExpression}
        />
      </PanelContextProvider>
    </ConfigPanel.ConfigOption>
  );
};

const Var = memo(VarComp);

const EmptyStateComp: FC = () => {
  return (
    <EmptyStateContainer>
      <EmptyStateHeader>Add source data</EmptyStateHeader>
      <EmptyStateBody>
        Write Weave expressions to import datasets, models, runs or artifacts
        and create new variables. Variables are the building blocks of dynamic
        Weave boards.
      </EmptyStateBody>
    </EmptyStateContainer>
  );
};

const EmptyState = memo(EmptyStateComp);

const VarBarContainer = styled.div`
  height: 100%;
  border-right: 1px solid ${GRAY_350};
`;

const EmptyStateContainer = styled.div`
  text-align: center;
  padding: 12px;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
`;

const EmptyStateHeader = styled.div`
  font-size: 20px;
  font-weight: 600;
`;

const EmptyStateBody = styled.div`
  margin-top: 8px;
  line-height: 140%;
`;
