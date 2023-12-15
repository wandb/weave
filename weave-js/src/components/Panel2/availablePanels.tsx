import {
  isAssignableTo,
  isListLike,
  isMediaTypeLike,
  isTypedDictLike,
  list,
  listObjectType,
  nullableTaggableValue,
  Stack,
  Type,
} from '@wandb/weave/core';
import * as _ from 'lodash';
import {useMemo} from 'react';

import {useDeepMemo} from '../../hookUtils';
import * as Panel from './panel';
import * as PanelLib from './panellib/libpanel';
import * as LibTypes from './panellib/libtypes';
import {getStackInfo, StackInfo} from './panellib/stackinfo';
import * as PanelRegistry from './PanelRegistry';
import {Spec as PanelTableMergeSpec} from './PanelTableMerge';

const getTypeHandlerStacksInternal = (currentType: Type) => {
  const stacks = LibTypes._getTypeHandlerStacks(
    currentType,
    PanelRegistry.PanelSpecs(),
    PanelRegistry.ConverterSpecs(),
    isAssignableTo
  );
  // Hack, sort execute to the top for now.
  // TODO: Be better
  return _.sortBy(stacks, stack => (stack.id.startsWith('execute') ? 0 : 1));
};

// We memoize this, because its currently called a lot and is pretty
// expensive.
const typeHandlerCache: {
  [type: string]: ReturnType<typeof getTypeHandlerStacksInternal>;
} = {};

const getTypeHandlerStacks = (currentType: Type) => {
  const typeId = JSON.stringify(currentType);
  let stacks = typeHandlerCache[typeId];
  if (stacks != null) {
    return stacks;
  }
  stacks = _.uniqBy(
    getTypeHandlerStacksInternal(currentType),
    stack => PanelLib.getStackIdAndName(stack).id
  );
  typeHandlerCache[typeId] = stacks;
  return stacks;
};

export type PanelStack = LibTypes.TypedInputHandlerStack<
  Type,
  Panel.PanelSpec,
  Panel.PanelConvertSpec
>;

function handlerStackLength(hs: PanelStack): number {
  if (PanelLib.isWithChild(hs)) {
    return 1 + handlerStackLength(hs.child);
  }
  return 1;
}

function panelStackType(hs: PanelStack): Type {
  if (PanelLib.isWithChild(hs)) {
    if (hs.id === 'row') {
      return {type: 'list', objectType: panelStackType(hs.child)};
    } else {
      throw new Error('Unhandled panel stack type: ' + hs.id);
    }
  }
  const spec = panelSpecById(hs.id);
  if (spec == null) {
    throw new Error(`No panel spec for ${hs.id}`);
  }
  return spec.inputType;
}

// This is the start of a better way to order panel recommendations.
// We want to use the panel with the most specific type. Not ready to go
// yet and will potentially change UI behavior a fair bit.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function handlerStackCompare(hs1: PanelStack, hs2: PanelStack) {
  const hs1Type = panelStackType(hs1);
  const hs2Type = panelStackType(hs2);
  const hs1ToHs2 = isAssignableTo(hs1Type, hs2Type);
  const hs2ToHs1 = isAssignableTo(hs2Type, hs1Type);
  if (hs1ToHs2 && hs2ToHs1) {
    const hs1Len = handlerStackLength(hs1);
    const hs2len = handlerStackLength(hs2);
    if (hs1Len === hs2len) {
      return 0;
    } else if (hs1Len < hs2len) {
      return -1;
    } else {
      return 1;
    }
  } else if (hs1ToHs2) {
    return -1;
  } else if (hs2ToHs1) {
    return 1;
  }
  // disjoint types, sort by name
  return hs1.id.localeCompare(hs2.id);
}

// This function determines the recommendation order!
function scoreHandlerStack(type: Type, hs: PanelStack) {
  const sidAndName = PanelLib.getStackIdAndName(hs);
  let scoreHs = 0;
  if (sidAndName.id.startsWith(PanelTableMergeSpec.id)) {
    scoreHs += 10;
  }

  if (sidAndName.id.endsWith('-file')) {
    scoreHs += 10;
  }

  if (
    sidAndName.id.startsWith('row') &&
    !isMediaTypeLike(listObjectType(nullableTaggableValue(type)))
  ) {
    scoreHs -= 5;
  }

  if (sidAndName.id.indexOf('row.row') > -1) {
    scoreHs -= 10;
  }

  // If its a panel that accepts list<any> (table, plot, etc), move it down,
  // unless our input type is list of dicts.
  if (
    !PanelLib.isWithChild(hs) &&
    isAssignableTo(
      {type: 'list', objectType: 'any'},
      panelSpecById(hs.id)!.inputType
    ) &&
    isListLike(type) &&
    !isTypedDictLike(
      nullableTaggableValue(listObjectType(nullableTaggableValue(type)))
    )
  ) {
    scoreHs -= 10;
  }

  // void is only assignable to any, use this to detect very permissive
  // panels and give them a low score.
  if (
    (isAssignableTo('invalid', hs.inputType) ||
      isAssignableTo(list('invalid'), hs.inputType)) &&
    hs.id !== 'table' &&
    !sidAndName.id.endsWith('plot')
  ) {
    scoreHs -= 15;
  }
  if (hs.inputType === 'any') {
    scoreHs -= 50;
  }
  if (sidAndName.id.indexOf('Facet') > -1) {
    scoreHs -= 10;
  }
  if (
    sidAndName.id.includes('Expression') ||
    sidAndName.id.includes('Auto') ||
    sidAndName.id.includes('object') ||
    sidAndName.id.includes('any-obj') ||
    sidAndName.id.includes('debug-expression-graph')
  ) {
    scoreHs -= 50;
  }

  // Until combined 2d projection performance is addressed, bump it down in the recommendation list (i.e. don't auto recommend it)
  if (sidAndName.id.includes('projection.plot')) {
    scoreHs -= 100;
  }

  return scoreHs;
}

// True if any panel in the stack has hidden: true
function stackHasHiddenPanel(panelStack: PanelStack): boolean {
  if (panelStack.hidden) {
    return true;
  }
  if (PanelLib.isWithChild(panelStack)) {
    return stackHasHiddenPanel(panelStack.child);
  }
  return false;
}

// Get the panels available for a given type. If a panelId is already
// chosen, pass it as the second argument. The curPanelId will match
// panelId if it is available, otherwise it will revert to the first
// available panel.
export interface GetPanelStacksForTypeOpts {
  excludeTable?: boolean;
  excludePlot?: boolean;
  excludeMultiTable?: boolean;
  excludeBarChart?: boolean;
  excludePanelPanel?: boolean;
  showDebug?: boolean;
  stackIdFilter?: (stackId: string) => boolean;
  allowedPanels?: string[];
  disallowedPanels?: string[];
}
export function getPanelStacksForType(
  type: Type,
  panelId: string | undefined,
  opts: GetPanelStacksForTypeOpts = {}
): {
  curPanelId: string | undefined;
  stackIds: StackInfo[];
  handler: PanelStack | undefined;
} {
  let handlerStacks = getTypeHandlerStacks(type);

  const allowedPanels = opts.allowedPanels;

  if (allowedPanels != null) {
    handlerStacks = handlerStacks.filter(hs =>
      allowedPanels!.includes(PanelLib.getStackIdAndName(hs).id)
    );
  } else {
    // Don't recommend hidden panels unless they match the current panelId
    handlerStacks = handlerStacks.filter(
      hs =>
        PanelLib.getStackIdAndName(hs).id === panelId ||
        !stackHasHiddenPanel(hs)
    );

    if (opts.excludeTable) {
      handlerStacks = handlerStacks.filter(
        hs =>
          !PanelLib.getStackIdAndName(hs).id.endsWith('table') &&
          !PanelLib.getStackIdAndName(hs).id.includes('wb_trace_tree-')
      );
    }
    if (opts.excludeMultiTable) {
      handlerStacks = handlerStacks.filter(
        hs =>
          !PanelLib.getStackIdAndName(hs).id.startsWith(PanelTableMergeSpec.id)
      );
    }
    if (opts.excludePlot) {
      handlerStacks = handlerStacks.filter(
        hs => !PanelLib.getStackIdAndName(hs).id.endsWith('plot')
      );
    }

    if (opts.excludeBarChart) {
      handlerStacks = handlerStacks.filter(
        hs => !PanelLib.getStackIdAndName(hs).id.endsWith('barchart')
      );
    }

    if (opts.excludePanelPanel) {
      handlerStacks = handlerStacks.filter(
        hs => !(PanelLib.getStackIdAndName(hs).id === 'panel')
      );
    }

    if (!opts.showDebug) {
      handlerStacks = handlerStacks.filter(
        hs => PanelLib.getStackIdAndName(hs).id.indexOf('debug') === -1
      );
    }
    if (opts.stackIdFilter != null) {
      handlerStacks = handlerStacks.filter(hs =>
        opts.stackIdFilter!(PanelLib.getStackIdAndName(hs).id)
      );
    }
    // make sure we only allow projection to flow into plot (for now)
    handlerStacks = handlerStacks.filter(
      hs =>
        PanelLib.getStackIdAndName(hs).id.indexOf('projection') === -1 ||
        PanelLib.getStackIdAndName(hs).id.endsWith('plot')
    );

    handlerStacks = handlerStacks.sort((hs1, hs2) => {
      return scoreHandlerStack(type, hs2) - scoreHandlerStack(type, hs1);
    });
  }

  if (opts.disallowedPanels != null) {
    handlerStacks = handlerStacks.filter(
      hs => !opts.disallowedPanels!.includes(PanelLib.getStackIdAndName(hs).id)
    );
  }

  if (handlerStacks.length > 1) {
    handlerStacks = handlerStacks.filter(
      hs => !PanelLib.getStackIdAndName(hs).id.endsWith('raw')
    );
  }

  const stackIds = handlerStacks.map(getStackInfo);
  const configuredStackIndex = stackIds.findIndex(si => si.id === panelId);
  let backupConfiguredStackIndex = -1;
  // If there is not an exact match...
  if (panelId != null && panelId !== '') {
    // Fallback to any panels which are converters to the current panel (example Table -> Merge.Table)
    backupConfiguredStackIndex = stackIds.findIndex(si =>
      si.id.endsWith(panelId)
    );

    // Fallback to the same initial converter (this is also helpful in converting from Row.Table-File to Row.Table)
    if (backupConfiguredStackIndex === -1) {
      backupConfiguredStackIndex = stackIds.findIndex(
        si => si.id.split('.')[0] === panelId.split('.')[0]
      );
    }
  }

  let curPanelId: string | undefined;
  if (configuredStackIndex !== -1) {
    curPanelId = panelId;
  } else if (backupConfiguredStackIndex !== -1) {
    curPanelId = stackIds[backupConfiguredStackIndex].id;
  } else if (stackIds.length > 0) {
    // Automatically choose a new panel.
    const autoPanelStacks = handlerStacks.filter(hs => {
      // Never choose something with Group
      return !PanelLib.getStackIdAndName(hs).id.includes('Group');
    });
    if (autoPanelStacks.length > 0) {
      curPanelId = PanelLib.getStackIdAndName(autoPanelStacks[0]).id;
    }
  }

  if (curPanelId === 'Group' && panelId !== 'Group') {
    // Don't automatically choose Group. Go to Expression instead.
    curPanelId = 'Expression';
  }

  const actualStackIndex = stackIds.findIndex(si => si.id === curPanelId);
  const handler =
    actualStackIndex !== -1 ? handlerStacks[actualStackIndex] : undefined;
  return {curPanelId, stackIds, handler};
}

export function usePanelStacksForType(
  type: Type,
  panelId: string | undefined,
  opts: GetPanelStacksForTypeOpts = {}
) {
  // Deep memo this so the caller doesn't have to worry about ref-equality
  opts = useDeepMemo(opts);
  return useMemo(
    () =>
      getPanelStacksForType(type, panelId, {
        ...opts,
        excludePlot: opts.excludePlot,
        excludeMultiTable: opts.excludeMultiTable || opts.excludeTable,
      }),
    [type, panelId, opts]
  );
}

// Get fixed dimensions for a panel stack.
// Regular panels can optionally set a defaultFixedSize. Converter
// panels can specify a function that computes a fixed size based on
// their child panel dimensions. This runs the chain of calls to
// get the top-level dimensions.

// export function getPanelStackDims<C>(
//   panelStack: PanelStack | undefined,
//   type: Types.Type,
//   config: C
export function getPanelStackDims<C, T extends Type>(
  panelStack: PanelStack | undefined,
  type: T,
  config: C
): {width: number | undefined; height: number | undefined} {
  if (panelStack == null) {
    return {width: undefined, height: undefined};
  }

  if (PanelLib.isWithChild(panelStack)) {
    const childDims = getPanelStackDims(
      panelStack.child,
      panelStack.convert(type)!,
      config
    );
    if (panelStack.defaultFixedSize != null) {
      // TODO: converter panels should be able to change their fixed
      // size based on their config. (e.g. the multi-container should
      // change its fixed size based on its page size). We need to
      // wire the nested config through here to do that. (We already
      // do something similar in PanelComp)
      // I wired type through, but config would be better...
      return panelStack.defaultFixedSize(childDims, type, config);
    }
    return {width: undefined, height: undefined};
    // const childDims = getPanelStackDims(panelStack.child, config);
    // return panelStack.defaultFixedSize != null
    //   ? panelStack.defaultFixedSize(childDims, config)
    //   : {width: undefined, height: undefined};
  }

  const {defaultFixedSize} = panelStack;
  const dimensions =
    typeof defaultFixedSize === 'function'
      ? defaultFixedSize(config)
      : defaultFixedSize;
  const {height, width} = dimensions ?? {};
  return {height, width};
}

export function panelIsOp(panelId: string): boolean {
  const panel = PanelRegistry.ConverterSpecs().find(p => p.id === panelId);
  if (panel == null) {
    return false;
  }
  return (panel as any).equivalentTransform != null;
}

export function getTransformPanel(panelId: string) {
  const panel = PanelRegistry.ConverterSpecs().find(p => p.id === panelId);
  if (panel == null) {
    return undefined;
  }
  return panel as unknown as Panel.PanelSpec;
}

export function panelSpecById(panelId: string) {
  return PanelRegistry.PanelSpecs().find(p => p.id === panelId);
}

// PanelPanel is currently not able to be nested within other childpanel
// based on stack, exclude panelpanel if nested
export const excludePanelPanel = (stack: Stack) => stack.length > 0;
