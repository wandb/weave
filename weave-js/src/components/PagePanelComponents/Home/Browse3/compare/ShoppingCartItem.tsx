/**
 * Draggable item representing one item being compared.
 */

import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import classNames from 'classnames';
import React, {useState} from 'react';
import {SortableElement, SortableHandle} from 'react-sortable-hoc';

import {Button} from '../../../../Button';
import {Icon} from '../../../../Icon';
import {Pill} from '../../../../Tag';
import {Tailwind} from '../../../../Tailwind';
import {Tooltip} from '../../../../Tooltip';
import {ShoppingCartItemDef} from './types';

// TODO: Change cursor to grabbing when dragging
const DragHandle = SortableHandle(() => (
  <div className="cursor-grab">
    <Icon name="drag-grip" />
  </div>
));

type ShoppingCartItemProps = {
  numItems: number;
  idx: number;
  item: ShoppingCartItemDef;
  baselineEnabled: boolean;
  isSelected: boolean;
  onClickShoppingCartItem: (value: string) => void;
  onSetBaseline: (value: string | null) => void;
  onRemoveShoppingCartItem: (value: string) => void;
};

export const ShoppingCartItem = SortableElement(
  ({
    numItems,
    idx,
    item,
    baselineEnabled,
    isSelected,
    onClickShoppingCartItem,
    onSetBaseline,
    onRemoveShoppingCartItem,
  }: ShoppingCartItemProps) => {
    const isSelectable = numItems > 2 && idx !== 0;
    const isDeletable = numItems > 2;
    const isBaseline = baselineEnabled && idx === 0;
    const [isOpen, setIsOpen] = useState(false);

    const onClickItem = isSelectable
      ? () => {
          onClickShoppingCartItem(item.value);
        }
      : undefined;

    const onMakeBaseline = (e: React.MouseEvent) => {
      e.stopPropagation();
      onSetBaseline(item.value);
    };

    const onRemoveItem = (e: React.MouseEvent) => {
      e.stopPropagation();
      onRemoveShoppingCartItem(item.value);
    };

    const inner = (
      <div
        className={classNames(
          'flex select-none items-center gap-4 whitespace-nowrap rounded-[4px] border-[1px] border-moon-250 bg-white px-4 py-8 text-sm font-semibold hover:border-moon-350 hover:bg-moon-100',
          {
            'border-teal-350 text-teal-500 outline outline-1 outline-teal-350':
              isSelected,
          },
          {
            'cursor-pointer': isSelectable,
          }
        )}
        onClick={onClickItem}>
        <DragHandle />
        <div className="flex items-center">
          {item.label ?? item.value}
          {isBaseline && (
            <Pill color="teal" label="Baseline" className="ml-8" />
          )}
        </div>
        <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
          <DropdownMenu.Trigger>
            <Button
              variant="ghost"
              icon="overflow-vertical"
              active={isOpen}
              size="small"
            />
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content align="start">
              {isBaseline ? (
                <DropdownMenu.Item
                  onClick={() => {
                    onSetBaseline(null);
                  }}>
                  <Icon name="baseline-alt" />
                  Remove baseline
                </DropdownMenu.Item>
              ) : (
                <DropdownMenu.Item onClick={onMakeBaseline}>
                  <Icon name="baseline-alt" />
                  Make baseline
                </DropdownMenu.Item>
              )}
              {isDeletable && (
                <>
                  <DropdownMenu.Separator />
                  <DropdownMenu.Item onClick={onRemoveItem}>
                    <Icon name="delete" />
                    Remove from comparison
                  </DropdownMenu.Item>
                </>
              )}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    );

    if (!isSelectable) {
      return <Tailwind>{inner}</Tailwind>;
    }

    return (
      <Tailwind>
        <Tooltip content="Click to select this item" trigger={inner} />
      </Tailwind>
    );
  }
);
