import React from 'react';
import {SortableContainer} from 'react-sortable-hoc';

import {EvaluationComparisonState} from '../../ecpState';
import {DraggableItem} from './DraggableItem';
import {ItemDef} from './DraggableItem';

type DraggableSectionProps = {
  state: EvaluationComparisonState;
  items: ItemDef[];
  onSetBaseline: (value: string | null) => void;
  onRemoveItem: (value: string) => void;
};

export const DraggableSection = SortableContainer(
  ({state, items, onSetBaseline, onRemoveItem}: DraggableSectionProps) => {
    return (
      <div className="flex flex-wrap items-center gap-16">
        {items.map((item, index) => (
          <DraggableItem
            key={`item-${item.value}`}
            numItems={items.length}
            index={index}
            idx={index}
            item={item}
            state={state}
            onRemoveItem={onRemoveItem}
            onSetBaseline={onSetBaseline}
          />
        ))}
      </div>
    );
  }
);
