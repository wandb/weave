import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import {Icon} from '@wandb/weave/components/Icon';
import {Pill} from '@wandb/weave/components/Tag/Pill';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React, {useState} from 'react';
import {SortableElement, SortableHandle} from 'react-sortable-hoc';

import {EvaluationComparisonState} from '../../ecpState';
import {EvaluationCallLink} from '../ComparisonDefinitionSection/EvaluationDefinition';

export type ItemDef = {
  key: string;
  value: string;
  label?: string;
};

type DraggableItemProps = {
  state: EvaluationComparisonState;
  item: ItemDef;
  numItems: number;
  idx: number;
  onRemoveItem: (value: string) => void;
  onSetBaseline: (value: string | null) => void;
};

export const DraggableItem = SortableElement(
  ({
    state,
    item,
    numItems,
    idx,
    onRemoveItem,
    onSetBaseline,
  }: DraggableItemProps) => {
    const isDeletable = numItems > 1;
    const isBaseline = idx === 0;
    const [isOpen, setIsOpen] = useState(false);

    const onMakeBaselinePropagated = (e: React.MouseEvent) => {
      e.stopPropagation();
      onSetBaseline(item.value);
    };

    const onRemoveItemPropagated = (e: React.MouseEvent) => {
      e.stopPropagation();
      onRemoveItem(item.value);
    };

    return (
      <Tailwind>
        <div
          className={classNames(
            'flex select-none items-center gap-4 whitespace-nowrap rounded-[4px] border-[1px] border-moon-250 bg-white px-4 py-8 text-sm font-semibold hover:border-moon-350 hover:bg-moon-100'
          )}>
          <DragHandle />
          <div className="flex items-center">
            <EvaluationCallLink callId={item.value} state={state} />
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
              <DropdownMenu.Content align="start" style={{zIndex: 9999}}>
                <DropdownMenu.Item
                  onClick={onMakeBaselinePropagated}
                  disabled={isBaseline}>
                  <Icon name="baseline-alt" />
                  Make baseline
                </DropdownMenu.Item>
                {isDeletable && (
                  <>
                    <DropdownMenu.Separator />
                    <DropdownMenu.Item onClick={onRemoveItemPropagated}>
                      <Icon name="delete" />
                      Remove from comparison
                    </DropdownMenu.Item>
                  </>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      </Tailwind>
    );
  }
);

const DragHandle = SortableHandle(() => (
  <div className="cursor-grab">
    <Icon name="drag-grip" />
  </div>
));
