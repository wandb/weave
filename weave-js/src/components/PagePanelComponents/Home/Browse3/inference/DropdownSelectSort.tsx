/**
 * Sort order selector for the model catalog page.
 */
import {Button} from '@wandb/weave/components/Button';
import * as DropdownMenu from '@wandb/weave/components/DropdownMenu';
import React from 'react';

import {Icon} from '../../../../Icon';

export type ModelTileSortOrder =
  | 'Popularity'
  | 'Newest'
  | 'Input price (low to high)'
  | 'Input price (high to low)'
  | 'Output price (low to high)'
  | 'Output price (high to low)'
  | 'Biggest context window';

type DropdownSelectSortProps = {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  sort: ModelTileSortOrder;
  setSort: (sort: ModelTileSortOrder) => void;
};

export const DropdownSelectSort = ({
  isOpen,
  onOpenChange,
  sort,
  setSort,
}: DropdownSelectSortProps) => {
  return (
    <DropdownMenu.Root open={isOpen} onOpenChange={onOpenChange}>
      <DropdownMenu.Trigger>
        <Button size="small" variant="secondary" active={isOpen}>
          <div className="flex items-center gap-2">
            Sort by: {sort} <Icon width={16} height={16} name="chevron-down" />
          </div>
        </Button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content align="start">
          <DropdownMenu.Item onClick={() => setSort('Popularity')}>
            <div className="flex w-full items-center justify-between gap-4">
              Popularity
              {sort === 'Popularity' && <Icon name="checkmark" />}
            </div>
          </DropdownMenu.Item>
          <DropdownMenu.Item onClick={() => setSort('Newest')}>
            <div className="flex w-full items-center justify-between gap-4">
              Newest
              {sort === 'Newest' && <Icon name="checkmark" />}
            </div>
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onClick={() => setSort('Input price (low to high)')}>
            <div className="flex w-full items-center justify-between gap-4">
              Input price (low to high)
              {sort === 'Input price (low to high)' && (
                <Icon name="checkmark" />
              )}
            </div>
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onClick={() => setSort('Input price (high to low)')}>
            <div className="flex w-full items-center justify-between gap-4">
              Input price (high to low)
              {sort === 'Input price (high to low)' && (
                <Icon name="checkmark" />
              )}
            </div>
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onClick={() => setSort('Output price (low to high)')}>
            <div className="flex w-full items-center justify-between gap-4">
              Output price (low to high)
              {sort === 'Output price (low to high)' && (
                <Icon name="checkmark" />
              )}
            </div>
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onClick={() => setSort('Output price (high to low)')}>
            <div className="flex w-full items-center justify-between gap-4">
              Output price (high to low)
              {sort === 'Output price (high to low)' && (
                <Icon name="checkmark" />
              )}
            </div>
          </DropdownMenu.Item>
          <DropdownMenu.Item onClick={() => setSort('Biggest context window')}>
            <div className="flex w-full items-center justify-between gap-4">
              Biggest context window
              {sort === 'Biggest context window' && <Icon name="checkmark" />}
            </div>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
};
