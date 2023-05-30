import {callOpVeryUnsafe, NodeOrVoidNode, varNode} from '@wandb/weave/core';
import produce from 'immer';
import * as _ from 'lodash';
import React, {useCallback, useMemo} from 'react';
import {Button, Icon, Menu, Popup} from 'semantic-ui-react';
import styled from 'styled-components';

import {getPanelStacksForType} from '../Panel2/availablePanels';
import {
  ChildPanelConfig,
  ChildPanelFullConfig,
  getFullChildPanel,
} from '../Panel2/ChildPanel';
import {emptyTable} from '../Panel2/PanelTable/tableState';
import {
  addChild,
  ensureDashboard,
  getPath,
  isGroupNode,
  makePanel,
  panelChildren,
  setPath,
} from '../Panel2/panelTree';

const OutlineItem = styled.div``;

const OutlineItemTitle = styled.div<{selected: boolean}>`
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
  padding: 2px 0;

  border: ${props => (props.selected ? '1px solid blue' : 'none')};

  &:hover {
    background-color: #ebfbff;
  }
`;

const OutlineItemChildren = styled.div`
  padding-left: 8px;
  // border-left: 1px solid #eee;
`;

const TitleContent = styled.div`
  width: 100%;

  & .ui.button {
    display: none;
  }

  &:hover .ui.button {
    display: inherit;
  }
`;

const ControlButton = styled(Button)`
  margin-right: -5px !important;
  padding: 5px !important;
  background: none !important;
  border: none !important;

  & > i {
    margin: 0 !important;
  }

  &:hover i {
    color: #56acfc !important;
  }
`;

export type OutlinePanelProps = OutlineProps & {
  name: string;
  localConfig: ChildPanelFullConfig;
  path: string[];
};

const OutlinePanel: React.FC<OutlinePanelProps> = props => {
  const {
    name,
    localConfig,
    selected,
    setSelected,
    path,
    config,
    updateConfig,
    updateConfig2,
  } = props;
  // item expand / collapse disabled for now, so we don't get the
  // const expandedState = React.useState(true);
  const expanded = true;
  const curPanelId = getPanelStacksForType(
    localConfig?.input_node?.type ?? 'invalid',
    localConfig?.id
  ).curPanelId;
  const children = panelChildren(localConfig); // TODO: curPanelId!

  const isSelected = path.join('.') === selected.join('.');
  // We need to derive the panel ID in case input type doesn't match
  // panel.id

  const handleDelete = useCallback(
    (ev: React.MouseEvent) => {
      ev.stopPropagation();

      updateConfig(
        produce(config, draft => {
          let cursor: any = draft;
          const remainingPath = path;
          while (remainingPath.length > 1) {
            const childPath = remainingPath.shift()!; // We'll always have an element to shift off here
            if (cursor.id === 'Group') {
              cursor = cursor.config.items[childPath];
            } else if (cursor.id === 'LabeledItem') {
              cursor = cursor.config[childPath];
            } else {
              throw new Error(
                `Outline delete failed: Cannot traverse config for panel id ${cursor.id}`
              );
            }
          }
          const lastStep = remainingPath.shift() as string;
          if (isGroupNode(cursor)) {
            delete cursor.config.items[lastStep];
            if (cursor.config?.gridConfig != null) {
              // Also remove from panelGrid.
              const index = cursor.config.gridConfig.panels.findIndex(
                p => p.id === lastStep
              );
              cursor.config.gridConfig.panels.splice(index, 1);
            }
          } else if (cursor.id === 'LabeledItem') {
            delete cursor.config[lastStep];
          } else {
            throw new Error(
              `Outline delete failed: Cannot traverse config for panel id ${cursor.id} (path = ${lastStep})`
            );
          }
        })
      );
    },
    [path, config, updateConfig]
  );

  const handleUnnest = useCallback(
    (panelPath: string[]) => {
      updateConfig2(oldConfig => {
        oldConfig = getFullChildPanel(oldConfig);
        const targetPanel = getPath(oldConfig, panelPath);
        if (!isGroupNode(targetPanel)) {
          throw new Error('Cannot unnest non-group panel');
        }
        const keys = Object.keys(targetPanel.config.items);
        if (keys.length === 0) {
          throw new Error('Cannot unnest empty group panel');
        }
        return setPath(oldConfig, panelPath, targetPanel.config.items[keys[0]]);
      });
    },
    [updateConfig2]
  );
  const handleSplit = useCallback(
    (panelPath: string[]) => {
      updateConfig2(oldConfig => {
        oldConfig = getFullChildPanel(oldConfig);
        const targetPanel = getPath(oldConfig, panelPath);
        const input = targetPanel.input_node;
        const splitPanel = makePanel(
          'Group',
          {
            items: {
              panel0: targetPanel,
              panel1: targetPanel,
            },
            layoutMode: 'vertical',
            equalSize: true,
          },
          input
        );

        return setPath(oldConfig, panelPath, splitPanel);
      });
    },
    [updateConfig2]
  );
  const handleAddToQueryBar = useCallback(
    (panelPath: string[]) => {
      updateConfig2(oldConfig => {
        oldConfig = getFullChildPanel(oldConfig);
        const targetPanel = getPath(oldConfig, panelPath);
        const input = targetPanel.input_node;
        const queryPanel = makePanel(
          'Query',
          {tableState: emptyTable()},
          input
        );

        const newTargetExpr = callOpVeryUnsafe('Query-selected', {
          self: varNode('any', 'panel0'),
        }) as NodeOrVoidNode;

        let root = setPath(oldConfig, panelPath, {
          ...targetPanel,
          input_node: newTargetExpr,
        });

        root = ensureDashboard(root);

        console.log('Query panel', queryPanel);

        root = addChild(root, ['sidebar'], queryPanel);

        return root;
      });
    },
    [updateConfig2]
  );
  const menuItems = useMemo(() => {
    const items = [
      {
        key: 'delete',
        content: 'Delete',
        icon: 'trash',
        onClick: handleDelete,
      },
    ];
    if (localConfig.id === 'Group') {
      items.push({
        key: 'unnest',
        content: 'Replace with first child',
        icon: 'level up',
        onClick: () => handleUnnest(path),
      });
    }
    items.push({
      key: 'split',
      content: 'Split',
      icon: 'columns',
      onClick: () => handleSplit(path),
    });
    if (path.find(p => p === 'main') != null && path.length > 1) {
      items.push({
        key: 'queryBar',
        content: 'Send to query bar',
        icon: 'arrow left',
        onClick: () => handleAddToQueryBar(path),
      });
    }
    return items;
  }, [
    handleAddToQueryBar,
    handleDelete,
    handleSplit,
    handleUnnest,
    localConfig.id,
    path,
  ]);

  const content = (
    <TitleContent>
      <Menu
        borderless
        style={{
          fontSize: 14,
          lineHeight: 20,
          border: 'none',
          boxShadow: 'none',
          minHeight: '20px',
          background: 'none',
        }}>
        <Menu.Menu style={{flex: '1 1 auto', height: '20px'}}>
          <Menu.Item style={{padding: 0, height: '20px'}}>
            <span>{name}</span>
            <span
              style={{marginLeft: '5px', color: '#bbb', fontStyle: 'italic'}}>
              {curPanelId}
            </span>
          </Menu.Item>
        </Menu.Menu>
        <Menu.Menu position="right" style={{flex: '0 0 auto', height: '20px'}}>
          {path.length > 0 ? (
            <Menu.Item style={{padding: 0, height: '20px'}}>
              <Popup
                basic
                style={{padding: 0}}
                on="click"
                position="bottom left"
                trigger={
                  <div>
                    <ControlButton>
                      <Icon name="ellipsis horizontal" size="small" />
                    </ControlButton>
                  </div>
                }
                content={
                  <Menu
                    compact
                    size="small"
                    items={menuItems}
                    secondary
                    vertical
                  />
                }
              />
            </Menu.Item>
          ) : null}
          {/* <Menu.Item style={{padding: 0, height: '20px'}}>
            <ControlButton onClick={handleRename}>
              <Icon name="pencil alternate" size="small" />
            </ControlButton>
          </Menu.Item> */}
        </Menu.Menu>
      </Menu>
    </TitleContent>
  );

  return children == null ? (
    <OutlineItem>
      <OutlineItemTitle
        onClick={() => {
          setSelected(path);
        }}
        selected={isSelected}>
        <Icon size="mini" name="chart bar" />
        {content}
      </OutlineItemTitle>
    </OutlineItem>
  ) : (
    <OutlineItem>
      <OutlineItemTitle
        onClick={() => {
          setSelected(path);
        }}
        selected={isSelected}>
        <Icon size="mini" name={expanded ? 'chevron down' : 'chevron right'} />
        {content}
      </OutlineItemTitle>
      {expanded && (
        <OutlineItemChildren>
          {_.map(children, (conf, key) => (
            <OutlinePanel
              key={key}
              name={key}
              // root config is passed all the way down so we can operate on the whole thing
              config={props.config}
              localConfig={conf}
              updateConfig={props.updateConfig}
              updateConfig2={props.updateConfig2}
              selected={selected}
              setSelected={setSelected}
              path={[...path, key]}
            />
          ))}
        </OutlineItemChildren>
      )}
    </OutlineItem>
  );
};

export interface OutlineProps {
  config: ChildPanelFullConfig;
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  updateConfig2: (
    change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig
  ) => void;
  selected: string[];
  setSelected: (path: string[]) => void;
}

export const Outline: React.FC<OutlineProps> = props => {
  return (
    <OutlinePanel
      name="root"
      // root config is passed all the way down so we can operate on the whole thing
      config={props.config}
      updateConfig={props.updateConfig}
      updateConfig2={props.updateConfig2}
      localConfig={props.config}
      selected={props.selected}
      setSelected={props.setSelected}
      path={[]}
    />
  );
};
