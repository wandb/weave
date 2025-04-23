/**
 * This name is an analogy - the collection of items that you have
 * "put in your basket" for comparison.
 */

import React from 'react';
import {useHistory} from 'react-router-dom';
import {SortableContainer} from 'react-sortable-hoc';

import {queryToggleString, searchParamsSetArray} from '../urlQueryUtil';
import {ShoppingCartItem} from './ShoppingCartItem';
import {ShoppingCartItemDefs} from './types';

type ShoppingCartItemsProps = {
  items: ShoppingCartItemDefs;
  baselineEnabled: boolean;
  selected: string | null;
};

type SortableItemsProps = ShoppingCartItemsProps & {
  onClickShoppingCartItem: (value: string) => void;
  onSetBaseline: (value: string | null) => void;
  onRemoveShoppingCartItem: (value: string) => void;
};

const SortableItems = SortableContainer(
  ({
    items,
    baselineEnabled,
    selected,
    onClickShoppingCartItem,
    onSetBaseline,
    onRemoveShoppingCartItem,
  }: SortableItemsProps) => {
    return (
      <div className="flex flex-wrap items-center gap-8">
        {items.map((item, index) => (
          <ShoppingCartItem
            key={`item-${item.value}`}
            numItems={items.length}
            index={index}
            idx={index}
            item={item}
            baselineEnabled={baselineEnabled}
            onClickShoppingCartItem={onClickShoppingCartItem}
            onSetBaseline={onSetBaseline}
            onRemoveShoppingCartItem={onRemoveShoppingCartItem}
            isSelected={item.value === selected}
          />
        ))}
      </div>
    );
  }
);

// Create a copy of the specified array, moving an item from one index to another.
function arrayMove<T>(array: readonly T[], from: number, to: number) {
  const slicedArray = array.slice();
  slicedArray.splice(
    to < 0 ? array.length + to : to,
    0,
    slicedArray.splice(from, 1)[0]
  );
  return slicedArray;
}

export const ShoppingCart = ({
  items,
  baselineEnabled,
  selected,
}: ShoppingCartItemsProps) => {
  const history = useHistory();

  const onSortEnd = ({
    oldIndex,
    newIndex,
  }: {
    oldIndex: number;
    newIndex: number;
  }) => {
    if (oldIndex === newIndex) {
      return;
    }
    const {search} = history.location;
    const params = new URLSearchParams(search);
    const newShoppingCartItems = arrayMove(items, oldIndex, newIndex);
    const values = newShoppingCartItems.map(i => i.value);
    searchParamsSetArray(params, items[0].key, values);
    if (newIndex === 0 && selected === newShoppingCartItems[0].value) {
      params.delete('sel');
    }
    history.replace({
      search: params.toString(),
    });
  };

  const onClickShoppingCartItem = (value: string) => {
    queryToggleString(history, 'sel', value);
  };

  const onSetBaseline = (value: string | null) => {
    const {search} = history.location;
    const params = new URLSearchParams(search);
    if (value === null) {
      params.delete('baseline');
    } else {
      let values = items.map(b => b.value);
      values = arrayMove(values, values.indexOf(value), 0);
      searchParamsSetArray(params, items[0].key, values);
      params.set('baseline', '1');
      if (selected === value) {
        params.delete('sel');
      }
    }
    history.replace({
      search: params.toString(),
    });
  };

  const onRemoveShoppingCartItem = (value: string) => {
    const newShoppingCartItems = items.filter(b => b.value !== value);
    const {search} = history.location;
    const params = new URLSearchParams(search);
    searchParamsSetArray(
      params,
      newShoppingCartItems[0].key,
      newShoppingCartItems.map(b => b.value)
    );
    if (selected === value || selected === newShoppingCartItems[0].value) {
      params.delete('sel');
    }
    history.replace({
      search: params.toString(),
    });
  };

  return (
    <SortableItems
      useDragHandle
      axis="xy"
      items={items}
      baselineEnabled={baselineEnabled}
      selected={selected}
      onSortEnd={onSortEnd}
      onClickShoppingCartItem={onClickShoppingCartItem}
      onSetBaseline={onSetBaseline}
      onRemoveShoppingCartItem={onRemoveShoppingCartItem}
    />
  );
};
