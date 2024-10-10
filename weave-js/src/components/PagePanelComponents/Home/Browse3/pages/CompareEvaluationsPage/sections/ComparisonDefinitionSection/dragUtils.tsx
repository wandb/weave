/***** COPIED FROM app/src/util/dragDrop.tsx *****/

import {WBIcon} from '@wandb/ui';
import {
  DragDropState,
  DragSourceProps,
  DropTargetProps,
} from '@wandb/weave/common/containers/DragDropContainer';
import * as globals from '@wandb/weave/common/css/globals.styles';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import styled from 'styled-components';

export type ReorderFn = (fromIndex: number, toIndex: number) => void;

type DropIndicatorPosition = `top` | `bottom` | `left` | `right`;

type DropIndicatorMode = `vertical` | `horizontal`;

type DropzonePadding = {[P in DropIndicatorPosition]: number};

const ZERO_DROPZONE_PADDING: DropzonePadding = {
  top: 0,
  bottom: 0,
  left: 0,
  right: 0,
};

const DROPZONE_PADDING_BUFFER_PX = 2;

type DragDropReorderParams = {
  reorder: ReorderFn;
  dropzonePadding?: Partial<DropzonePadding> | number;
  dropIndicatorMode?: DropIndicatorMode;
};

type DragDropReorder = {
  makeDragSourceCallbackRef: (
    itemIndex: number
  ) => (el: HTMLElement | null) => void;
  renderDropIndicators: (itemIndex: number) => React.ReactNode;
} & Pick<DropTargetProps, `onDragOver` | `onDrop`> &
  Pick<DragSourceProps, `onDragEnd`>;

export function useDragDropReorder({
  reorder,
  dropzonePadding: dropzonePaddingOption = ZERO_DROPZONE_PADDING,
  dropIndicatorMode = `vertical`,
}: DragDropReorderParams): DragDropReorder {
  // Dropzone padding

  const dropzonePaddingNormalized: DropzonePadding =
    typeof dropzonePaddingOption === `number`
      ? {
          top: dropzonePaddingOption,
          bottom: dropzonePaddingOption,
          left: dropzonePaddingOption,
          right: dropzonePaddingOption,
        }
      : {...ZERO_DROPZONE_PADDING, ...dropzonePaddingOption};

  const dropzonePadding = useMemo(
    () => dropzonePaddingNormalized,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      dropzonePaddingNormalized.top,
      dropzonePaddingNormalized.bottom,
      dropzonePaddingNormalized.left,
      dropzonePaddingNormalized.right,
    ]
  );

  // Drag source refs

  const dragSourceByItemIndexRef = useRef<Map<number, HTMLElement | null>>(
    new Map()
  );

  const makeDragSourceCallbackRef = useCallback((itemIndex: number) => {
    return (el: HTMLElement | null) => {
      dragSourceByItemIndexRef.current.set(itemIndex, el);
    };
  }, []);

  // Drop indicator lines

  const [dropIndicatorItemIndex, setDropIndicatorItemIndex] = useState<
    number | null
  >(null);

  const [dropIndicatorPosition, setDropIndicatorPosition] =
    useState<DropIndicatorPosition | null>(null);

  const setDropIndicatorPositionForMode = useCallback(
    (reorderTargetIndex: number, draggedItemIndex: number) => {
      switch (dropIndicatorMode) {
        case `vertical`:
          setDropIndicatorPosition(
            reorderTargetIndex < draggedItemIndex ? `left` : `right`
          );
          return;
        case `horizontal`:
          setDropIndicatorPosition(
            reorderTargetIndex < draggedItemIndex ? `top` : `bottom`
          );
          return;
      }
    },
    [dropIndicatorMode]
  );

  const clearDropIndicator = useCallback(() => {
    setDropIndicatorItemIndex(null);
    setDropIndicatorPosition(null);
  }, []);

  const renderDropIndicators = useCallback(
    (itemIndex: number): React.ReactNode => {
      if (dropIndicatorItemIndex !== itemIndex) {
        return null;
      }
      return (
        <>
          <DropIndicatorOverlay />
          {dropIndicatorPosition != null && (
            <DropIndicatorLine
              paddingZone={dropzonePadding[dropIndicatorPosition]}
              position={dropIndicatorPosition}
            />
          )}
        </>
      );
    },
    [dropIndicatorItemIndex, dropIndicatorPosition, dropzonePadding]
  );

  // Reorder helper functions

  const findReorderTargetIndex: (
    ctx: DragDropState,
    e: React.DragEvent
  ) => number | null = useCallback(
    (ctx, e) => {
      const draggedItemIndex = getDraggedItemIndex(ctx);
      if (draggedItemIndex == null) {
        return null;
      }

      const [x, y] = [e.clientX, e.clientY];

      const entries = _.sortBy(
        [...dragSourceByItemIndexRef.current.entries()],
        ([itemIndex]) => itemIndex
      );

      const reorderTargetEntry = entries.find(([itemIndex, el]) => {
        if (draggedItemIndex === itemIndex || el == null) {
          return false;
        }

        const {top, bottom, left, right} = el.getBoundingClientRect();
        return (
          x - DROPZONE_PADDING_BUFFER_PX >= left - dropzonePadding[`left`] &&
          x + DROPZONE_PADDING_BUFFER_PX <= right + dropzonePadding[`right`] &&
          y - DROPZONE_PADDING_BUFFER_PX >= top - dropzonePadding[`top`] &&
          y + DROPZONE_PADDING_BUFFER_PX <= bottom + dropzonePadding[`bottom`]
        );
      });

      return reorderTargetEntry?.[0] ?? null;
    },
    [dropzonePadding]
  );

  // Event handlers

  const updateIndicator: DropTargetProps[`onDragOver`] = useCallback(
    (ctx: DragDropState, e: React.DragEvent) => {
      const draggedItemIndex = getDraggedItemIndex(ctx);
      if (draggedItemIndex == null) {
        return;
      }

      const reorderTargetIndex = findReorderTargetIndex(ctx, e);
      if (reorderTargetIndex == null) {
        clearDropIndicator();
        return;
      }

      setDropIndicatorItemIndex(reorderTargetIndex);
      setDropIndicatorPositionForMode(reorderTargetIndex, draggedItemIndex);
    },
    [
      findReorderTargetIndex,
      clearDropIndicator,
      setDropIndicatorPositionForMode,
    ]
  );

  const triggerReorder: DropTargetProps[`onDrop`] = useCallback(
    (ctx: DragDropState, e: React.DragEvent) => {
      const draggedItemIndex = getDraggedItemIndex(ctx);
      if (draggedItemIndex == null) {
        return;
      }

      clearDropIndicator();

      const reorderTargetIndex = findReorderTargetIndex(ctx, e);
      if (reorderTargetIndex == null) {
        return;
      }

      reorder(draggedItemIndex, reorderTargetIndex);
    },
    [findReorderTargetIndex, clearDropIndicator, reorder]
  );

  useEffect(() => {
    document.addEventListener(`dragover`, clearDropIndicator);
    return () => {
      document.removeEventListener(`dragover`, clearDropIndicator);
    };
  }, [clearDropIndicator]);

  return {
    makeDragSourceCallbackRef,
    renderDropIndicators,
    onDragOver: updateIndicator,
    onDragEnd: clearDropIndicator,
    onDrop: triggerReorder,
  };
}

function getDraggedItemIndex(ctx: DragDropState): number | null {
  const draggedItemIndexStr = ctx.dragRef?.id;
  if (draggedItemIndexStr == null) {
    return null;
  }
  return Number(draggedItemIndexStr);
}

const DropIndicatorOverlay = styled.div`
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: rgba(221, 237, 252, 0.5);
  z-index: 1;
`;

const DROP_INDICATOR_LINE_WIDTH_PX = 2;

const DropIndicatorLine = styled.div<{
  paddingZone: number;
  position: DropIndicatorPosition;
}>`
  position: absolute;
  background-color: ${globals.primary};

  ${p => {
    switch (p.position) {
      case `top`:
        return `
          left: 0;
          right: 0;
          top: -${p.paddingZone + DROP_INDICATOR_LINE_WIDTH_PX / 2}px;
          height: ${DROP_INDICATOR_LINE_WIDTH_PX}px;
        `;
      case `bottom`:
        return `
          left: 0;
          right: 0;
          bottom: -${p.paddingZone + DROP_INDICATOR_LINE_WIDTH_PX / 2}px;
          height: ${DROP_INDICATOR_LINE_WIDTH_PX}px;
        `;
      case `left`:
        return `
          top: 0;
          bottom: 0;
          left: -${p.paddingZone + DROP_INDICATOR_LINE_WIDTH_PX / 2}px;
          width: ${DROP_INDICATOR_LINE_WIDTH_PX}px;
        `;
      case `right`:
        return `
          top: 0;
          bottom: 0;
          right: -${p.paddingZone + DROP_INDICATOR_LINE_WIDTH_PX / 2}px;
          width: ${DROP_INDICATOR_LINE_WIDTH_PX}px;
        `;
    }
  }}
`;

export const DragHandleIcon = styled(WBIcon).attrs({name: 'vertical-handle'})`
  font-size: 26px;
  border-radius: 50%;
  color: gray300;
  user-select: none;
  cursor: grab;
  &&&:hover {
    background: gray100;
    color: black;
  }
  &:active {
    cursor: grabbing;
  }
`;
DragHandleIcon.displayName = 'S.DragHandle';
