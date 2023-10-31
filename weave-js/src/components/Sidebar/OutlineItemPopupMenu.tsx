import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {useIsViewerWandbEmployee} from '@wandb/weave/common/hooks/useViewerIsWandbEmployee';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {produce} from 'immer';
import React, {memo, useCallback, useMemo} from 'react';
import styled from 'styled-components';

import {getFullChildPanel} from '../Panel2/ChildPanel';
import {
  addChild,
  getPath,
  isGroupNode,
  makePanel,
  setPath,
} from '../Panel2/panelTree';
import {OutlinePanelProps} from './Outline';
import {
  IconAddNew,
  IconCopy,
  IconDelete,
  IconRetry,
  IconSplit,
} from '../Panel2/Icons';
import {useSetInteractingPanel} from '../Panel2/PanelInteractContext';

const Divider = styled.div`
  margin: 0 -15px;
  border: 0.5px solid ${MOON_250};
  width: 200%;
`;

export type OutlineItemPopupMenuProps = Pick<
  OutlinePanelProps,
  `config` | `localConfig` | `path` | `updateConfig` | `updateConfig2`
> & {
  goBackToOutline?: () => void;
  trigger: JSX.Element;
  onClose?: () => void;
  onOpen?: () => void;
  isOpen: boolean;
};

const OutlineItemPopupMenuComp: React.FC<OutlineItemPopupMenuProps> = ({
  config,
  localConfig,
  path,
  updateConfig,
  updateConfig2,
  goBackToOutline,
  trigger,
  onClose,
  onOpen,
  isOpen,
}) => {
  const isViewerWandbEmployee = useIsViewerWandbEmployee();
  const setInteractingPanel = useSetInteractingPanel();
  const {isNumItemsLocked} = config.config;

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

      goBackToOutline?.();
    },
    [path, config, updateConfig, goBackToOutline]
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

      goBackToOutline?.();
    },
    [updateConfig2, goBackToOutline]
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

      goBackToOutline?.();
    },
    [updateConfig2, goBackToOutline]
  );
  const handleDuplicate = useCallback(
    (panelPath: string[]) => {
      updateConfig2(oldConfig => {
        oldConfig = getFullChildPanel(oldConfig);
        const targetPanel = getPath(oldConfig, panelPath);
        return addChild(oldConfig, panelPath.slice(0, -1), targetPanel);
      });

      goBackToOutline?.();
    },
    [updateConfig2, goBackToOutline]
  );
  const menuItems = useMemo(() => {
    const items = [];
    if (localConfig?.id === 'Group') {
      items.push({
        key: 'unnest',
        content: 'Replace with first child',
        icon: <IconRetry />,
        onClick: () => handleUnnest(path),
      });
    }

    if (!isNumItemsLocked) {
      items.push({
        key: 'duplicate',
        content: 'Duplicate',
        icon: <IconCopy />,
        onClick: () => handleDuplicate(path),
      });
    }

    if (path.find(p => p === 'main') != null && path.length > 1) {
      items.push({
        key: 'split',
        content: 'Split',
        icon: <IconSplit />,
        onClick: () => handleSplit(path),
      });

      if (isViewerWandbEmployee) {
        items.push({
          key: 'divider-0',
          content: <Divider />,
          disabled: true,
        });
        items.push({
          key: 'export-report',
          content: 'Add to report...',
          icon: <IconAddNew />,
          onClick: () => setInteractingPanel('export-report', path),
        });
      }
    }

    if (!isNumItemsLocked) {
      items.push({
        key: 'divider-1',
        content: <Divider />,
        disabled: true,
      });
      items.push({
        key: 'delete',
        content: 'Delete',
        icon: <IconDelete />,
        onClick: handleDelete,
      });
    }

    return items;
  }, [
    localConfig?.id,
    isNumItemsLocked,
    path,
    handleDelete,
    handleUnnest,
    handleDuplicate,
    isViewerWandbEmployee,
    handleSplit,
    setInteractingPanel,
  ]);

  if (!menuItems.length) {
    return null;
  }

  return (
    <DropdownMenu.Root
      open={isOpen}
      onOpenChange={open => (open ? onOpen?.() : onClose?.())}>
      <DropdownMenu.Trigger>
        {React.cloneElement(trigger, {active: isOpen})}
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          className="z-[100]"
          onCloseAutoFocus={e => e.preventDefault()}>
          {menuItems.map(item => (
            <DropdownMenu.Item
              key={item.key}
              onClick={item.onClick}
              disabled={item.disabled}>
              {item.icon}
              {item.content}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
};

export const OutlineItemPopupMenu = memo(OutlineItemPopupMenuComp);
