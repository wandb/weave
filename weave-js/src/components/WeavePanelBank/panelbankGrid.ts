import {cloneDeep, findIndex, isNaN, max} from 'lodash';

import {LayoutParameters} from './panelbank';

/* PanelBank grid section utils */
/* Borrowed heavily from https://github.com/STRML/react-grid-layout! */

export const GRID_COLUMN_COUNT = 24; // number of grid columns
export const GRID_ROW_HEIGHT = 32; // height of grid row in px
export const GRID_CONTAINER_PADDING = [32, 0]; // padding of grid container
export const GRID_ITEM_MARGIN = [16, 16]; // margin around each grid item
export const GRID_ITEM_DEFAULT_WIDTH = 24;
export const GRID_ITEM_DEFAULT_HEIGHT = 6;

export type GridLayoutItem = LayoutParameters & {
  id: string;
  moved?: boolean;
};

export type GridLayout = GridLayoutItem[];

export interface PanelLayout {
  layout: LayoutParameters;
}

/**
 * Get a layout item by ID. Used so we can override later on if necessary.
 *
 * @param  {Array}  layout Layout array.
  // React.useEffect(() => {
  //   if (props.value === '' && document.querySelector(':focus') == null) {
  //     ref.current?.focus();
  //   }
  // }, [props.value]);
 * @param  {String} id     ID
 * @return {LayoutItem}    Item at ID.
 */
export function getLayoutItem(
  layout: GridLayout,
  id: string
): GridLayoutItem | undefined {
  for (let i = 0, len = layout.length; i < len; i++) {
    if (layout[i].id === id) {
      return layout[i];
    }
  }
  return undefined;
}

/**
 * Get layout items sorted from top left to right and down.
 *
 * @return {Array} Array of layout objects.
 * @return {Array}        Layout, sorted static items first.
 */
export function sortLayoutItems(layoutItems: GridLayout): GridLayout {
  // return [].concat(layout).sort((a, b) => {
  return cloneDeep(layoutItems).sort((a, b) => {
    if (a.y > b.y || (a.y === b.y && a.x > b.x)) {
      return 1;
    } else if (a.y === b.y && a.x === b.x) {
      // Without this, we can get different sort results in IE vs. Chrome/FF
      return 0;
    }
    return -1;
  });
}

/**
 * Move an element. Responsible for doing cascading movements of other elements.
 *
 * @param  {Array}      layout            Full layout to modify.
 * @param  {LayoutItem} l                 element to move.
 * @param  {Number}     [x]               X position in grid units.
 * @param  {Number}     [y]               Y position in grid units.
 */
export function moveGridItem(
  layout: GridLayout,
  l: GridLayoutItem,
  x: number | undefined,
  y: number | undefined,
  isUserAction: boolean,
  // preventCollision: boolean,
  // compactType: CompactType,
  cols: number
): GridLayout {
  // if (l.static) {
  //   return layout;
  // }

  // Short-circuit if nothing to do.
  if (l.y === y && l.x === x) {
    return layout;
  }

  // console.log(
  //   `Moving element ${l.i} to [${String(x)},${String(y)}] from [${l.x},${l.y}]`
  // );
  // const oldX = l.x;
  const oldY = l.y;

  // This is quite a bit faster than extending the object
  if (typeof x === 'number') {
    l.x = x;
  }
  if (typeof y === 'number') {
    l.y = y;
  }
  l.moved = true;

  // Prevent dragging past the right edge of the grid
  if (l.x + l.w > cols) {
    l.x = cols - l.w;
  }

  // If this collides with anything, move it.
  // When doing this comparison, we have to sort the items we compare with
  // to ensure, in the case of multiple collisions, that we're getting the
  // nearest collision.
  // let sorted = sortLayoutItems(layout, compactType);
  // const movingUp =
  //   compactType === 'vertical' && typeof y === 'number'
  //     ? oldY >= y
  //     : compactType === 'horizontal' && typeof x === 'number'
  //     ? oldX >= x
  //     : false;
  let sorted = sortLayoutItems(layout);
  const movingUp = y && oldY >= y;

  // const movingUp =
  //   compactType === 'vertical' && typeof y === 'number'
  //     ? oldY >= y
  //     : compactType === 'horizontal' && typeof x === 'number'
  //     ? oldX >= x
  //     : false;
  if (movingUp) {
    sorted = sorted.reverse();
  }
  const collisions = getAllCollisions(sorted, l);

  // There was a collision; abort
  // if (preventCollision && collisions.length) {
  //   // console.log(`Collision prevented on ${l.i}, reverting.`);
  //   l.x = oldX;
  //   l.y = oldY;
  //   l.moved = false;
  //   return layout;
  // }

  // Move each item that collides away from this element.
  for (let i = 0, len = collisions.length; i < len; i++) {
    const collision = collisions[i];
    // console.log(
    //   `Resolving collision between ${l.i} at [${l.x},${l.y}] and ${
    //     collision.i
    //   } at [${collision.x},${collision.y}]`
    // );

    // Short circuit so we can't infinite loop
    if (collision.moved) {
      continue;
    }

    // // Don't move static items - we have to move *this* element away
    // if (collision.static) {
    //   layout = moveGridItemAwayFromCollision(
    //     layout,
    //     collision,
    //     l,
    //     isUserAction,
    //     compactType,
    //     cols
    //   );
    // } else {
    layout = moveGridItemAwayFromCollision(
      layout,
      l,
      collision,
      isUserAction,
      // compactType,
      cols
    );
  }

  return layout;
}

/**
 * This is where the magic needs to happen - given a collision, move an element away from the collision.
 * We attempt to move it up if there's room, otherwise it goes below.
 *
 * @param  {Array} layout            Full layout to modify.
 * @param  {LayoutItem} collidesWith Layout item we're colliding with.
 * @param  {LayoutItem} itemToMove   Layout item we're moving.
 */
export function moveGridItemAwayFromCollision(
  layout: GridLayout,
  collidesWith: GridLayoutItem,
  itemToMove: GridLayoutItem,
  isUserAction: boolean,
  // compactType: CompactType,
  cols: number
): GridLayout {
  // const compactH = false; // compactType === "horizontal";
  // // Compact vertically if not set to horizontal
  // const compactV = true; // compactType !== "horizontal";
  // const preventCollision = false; // we're already colliding

  // If there is enough space above the collision to put this element, move it there.
  // We only do this on the main collision as this can get funky in cascades and cause
  // unwanted swapping behavior.
  if (isUserAction) {
    // Reset isUserAction flag because we're not in the main collision anymore.
    isUserAction = false;

    // Make a mock item so we don't modify the item here, only modify in moveGridItem.
    const fakeItem: GridLayoutItem = {
      // x: compactH ? Math.max(collidesWith.x - itemToMove.w, 0) : itemToMove.x,
      // y: compactV ? Math.max(collidesWith.y - itemToMove.h, 0) : itemToMove.y,
      x: itemToMove.x,
      y: Math.max(collidesWith.y - itemToMove.h, 0),
      w: itemToMove.w,
      h: itemToMove.h,
      id: '-1',
    };

    // No collision? If so, we can go up there; otherwise, we'll end up moving down as normal
    if (!getFirstCollision(layout, fakeItem)) {
      // console.log(
      //   `Doing reverse collision on ${itemToMove.i} up to [${fakeItem.x},${
      //     fakeItem.y
      //   }].`
      // );
      return moveGridItem(
        layout,
        itemToMove,
        // compactH ? fakeItem.x : undefined,
        // compactV ? fakeItem.y : undefined,
        undefined,
        fakeItem.y,
        isUserAction,
        // preventCollision,
        // compactType,
        cols
      );
    }
  }

  return moveGridItem(
    layout,
    itemToMove,
    // compactH ? itemToMove.x + 1 : undefined,
    // compactV ? itemToMove.y + 1 : undefined,
    undefined,
    itemToMove.y + 1,
    isUserAction,
    // preventCollision,
    // compactType,
    cols
  );
}

/**
 * Returns the first item this layout collides with.
 * It doesn't appear to matter which order we approach this from, although
 * perhaps that is the wrong thing to do.
 *
 * @param  {Object} layoutItem Layout item.
 * @return {Object|undefined}  A colliding layout item, or undefined.
 */
export function getFirstCollision(
  layout: GridLayout,
  layoutItem: GridLayoutItem
): GridLayoutItem | undefined {
  for (let i = 0, len = layout.length; i < len; i++) {
    if (collides(layout[i], layoutItem)) {
      return layout[i];
    }
  }
  return undefined;
}

export function getAllCollisions(
  layout: GridLayout,
  layoutItem: GridLayoutItem
): GridLayout {
  return layout.filter(l => collides(l, layoutItem));
}

/**
 * Given two layoutitems, check if they collide.
 */
export function collides(l1: GridLayoutItem, l2: GridLayoutItem): boolean {
  if (l1.id === l2.id) {
    return false;
  } // same element
  if (
    isNaN(l1.x) ||
    isNaN(l1.y) ||
    isNaN(l1.w) ||
    isNaN(l1.h) ||
    isNaN(l2.x) ||
    isNaN(l2.y) ||
    isNaN(l2.w) ||
    isNaN(l2.h)
  ) {
    return false;
  }
  if (l1.x + l1.w <= l2.x) {
    return false;
  } // l1 is left of l2
  if (l1.x >= l2.x + l2.w) {
    return false;
  } // l1 is right of l2
  if (l1.y + l1.h <= l2.y) {
    return false;
  } // l1 is above l2
  if (l1.y >= l2.y + l2.h) {
    return false;
  } // l1 is below l2
  return true; // boxes overlap
}

/**
 * Given a layout, compact it. This involves going down each y coordinate and removing gaps
 * between items.
 *
 * @param  {Array} layout Layout.
 * @param  {Boolean} verticalCompact Whether or not to compact the layout
 *   vertically.
 * @return {Array}       Compacted Layout.
 */
export function compact(
  layout: GridLayout,
  // compactType: CompactType,
  cols: number
): GridLayout {
  // Statics go in the compareWith array right away so items flow around them.
  // const compareWith = getStatics(layout);
  const compareWith = []; // getStatics(layout);
  // We go through the items by row and column.
  // const sorted = sortLayoutItems(layout, compactType);
  const sorted = sortLayoutItems(layout); // , compactType);
  // Holding for new items.
  const out = Array(layout.length);

  for (let i = 0, len = sorted.length; i < len; i++) {
    let l = cloneLayoutItem(sorted[i]);

    // Don't move static elements
    // if (!l.static) {
    // l = compactItem(compareWith, l, compactType, cols, sorted);
    l = compactItem(compareWith, l, cols, sorted);
    // console.log(
    //   layout,
    //   sorted,
    //   sorted[i],
    //   layout.indexOf(sorted[i]),
    //   findIndex(layout, {i: sorted[i].i})
    // );

    // Add to comparison array. We only collide with items before this one.
    // Statics are already in this array.
    compareWith.push(l);
    // }

    // Add to output array to make sure they still come out in the right order.
    // out[layout.indexOf(sorted[i])] = l;
    out[findIndex(layout, {id: sorted[i].id})] = l;

    // Clear moved flag, if it exists.
    l.moved = false;
  }

  return out;
}

/**
 * Compact an item in the layout.
 */
export function compactItem(
  compareWith: GridLayout,
  l: GridLayoutItem,
  // compactType: CompactType,
  cols: number,
  fullLayout: GridLayout
): GridLayoutItem {
  // const compactV = true; // compactType === "vertical";
  // const compactH = false; // compactType === "horizontal";
  // if (compactV) {
  // Bottom 'y' possible is the bottom of the layout.
  // This allows you to do nice stuff like specify {y: Infinity}
  // This is here because the layout must be sorted in order to get the correct bottom `y`.
  l.y = Math.max(0, Math.min(bottom(compareWith), l.y));

  // } else if (compactH) {
  //   l.y = Math.min(bottom(compareWith), l.y);
  //   // Move the element left as far as it can go without colliding.
  //   while (l.x > 0 && !getFirstCollision(compareWith, l)) {
  //     l.x--;
  //   }
  // }

  // Move it down, and keep moving it down if it's colliding.
  let collision = getFirstCollision(compareWith, l);
  while (collision) {
    // if (compactH) {
    //   resolveCompactionCollision(fullLayout, l, collision.x + collision.w, 'x');
    // } else {
    resolveCompactionCollision(fullLayout, l, collision.y + collision.h, 'y');
    // }
    // // Since we can't grow without bounds horizontally, if we've overflown, let's move it down and try again.
    // if (compactH && l.x + l.w > cols) {
    //   l.x = cols - l.w;
    //   l.y++;
    // }
    collision = getFirstCollision(compareWith, l);
  }
  return l;
}

/**
 * Before moving item down, it will check if the movement will cause collisions and move those items down before.
 */
function resolveCompactionCollision(
  layout: GridLayout,
  item: GridLayoutItem,
  moveToCoord: number,
  axis: 'x' | 'y'
) {
  const heightWidth = {x: 'w', y: 'h'};
  const sizeProp = heightWidth[axis];
  item[axis] += 1;
  const itemIndex = layout
    .map(layoutItem => {
      return layoutItem.id;
    })
    .indexOf(item.id);

  // Go through each item we collide with.
  for (let i = itemIndex + 1; i < layout.length; i++) {
    const otherItem = layout[i];
    // Ignore static items
    // if (otherItem.static) { continue; }

    // Optimization: we can break early if we know we're past this el
    // We can do this b/c it's a sorted layout
    if (otherItem.y > item.y + item.h) {
      break;
    }

    if (collides(item, otherItem)) {
      resolveCompactionCollision(
        layout,
        otherItem,
        moveToCoord + item[sizeProp as 'w' | 'h'],
        axis
      );
    }
  }

  item[axis] = moveToCoord;
}

/**
 * Return the bottom coordinate of the layout.
 *
 * @param  {Array} layout Layout array.
 * @return {Number}       Bottom coordinate.
 */
export function bottom(layout: GridLayout): number {
  let maxY = 0;
  let bottomY;
  for (let i = 0, len = layout.length; i < len; i++) {
    bottomY = layout[i].y + layout[i].h;
    if (bottomY > maxY) {
      maxY = bottomY;
    }
  }
  return maxY;
}

// Fast path to cloning, since this is monomorphic
export function cloneLayoutItem(layoutItem: GridLayoutItem): GridLayoutItem {
  return {
    w: layoutItem.w,
    h: layoutItem.h,
    x: layoutItem.x,
    y: layoutItem.y,
    id: layoutItem.id,
    // minW: layoutItem.minW,
    // maxW: layoutItem.maxW,
    // minH: layoutItem.minH,
    // maxH: layoutItem.maxH,
    moved: Boolean(layoutItem.moved),
    // static: Boolean(layoutItem.static),
    // These can be null
    // isDraggable: layoutItem.isDraggable,
    // isResizable: layoutItem.isResizable
  };
}

export function findNextPanelLoc(
  layouts: LayoutParameters[],
  gridWidth?: number, // number of columns (not px)
  panelWidth?: number // number of columns (not px)
) {
  gridWidth = gridWidth || GRID_COLUMN_COUNT;
  panelWidth = panelWidth || GRID_ITEM_DEFAULT_WIDTH;
  const columnBottoms = new Array(gridWidth).fill(0);
  for (const panel of layouts) {
    const panelBottom = panel.y + panel.h;
    for (let x = panel.x; x < panel.x + panel.w; x++) {
      columnBottoms[x] = Math.max(columnBottoms[x], panelBottom);
    }
  }
  const candidates = [];
  for (let x = 0; x < gridWidth - panelWidth + 1; x++) {
    candidates.push(max(columnBottoms.slice(x, x + panelWidth)));
  }
  // argmin
  let min = candidates[0];
  let argmin = 0;
  for (let x = 1; x < candidates.length; x++) {
    if (candidates[x] < min) {
      min = candidates[x];
      argmin = x;
    }
  }
  const result = {x: argmin, y: min};
  return result;
}

export function getNewGridItemLayout(
  gridLayout: GridLayout | LayoutParameters[]
): LayoutParameters {
  return {
    ...findNextPanelLoc(gridLayout, GRID_COLUMN_COUNT, GRID_ITEM_DEFAULT_WIDTH),
    w: GRID_ITEM_DEFAULT_WIDTH,
    h: GRID_ITEM_DEFAULT_HEIGHT,
  };
}

export function getFullWidthPanelLayout(): LayoutParameters {
  return {
    x: 0,
    y: 0,
    w: GRID_COLUMN_COUNT,
    h: 8,
  };
}
