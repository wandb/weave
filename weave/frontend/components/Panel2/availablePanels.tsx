import * as _ from 'lodash';
import {useMemo, useContext} from 'react';
import * as Panel from './panel';
import * as PanelLib from './panellib/libpanel';
import * as Types from '@wandb/cg/browser/model/types';
import * as LibTypes from './panellib/libtypes';
import {Spec as PanelTableMergeSpec} from './PanelTableMerge';
import {useDeepMemo} from '@wandb/common/state/hooks';
import WeaveAppContext from '@wandb/common/cgreact.WeaveAppContext';
import * as PanelRegistry from './PanelRegistry';

const getTypeHandlerStacksInternal = (currentType: Types.Type) => {
  const stacks = LibTypes._getTypeHandlerStacks(
    currentType,
    PanelRegistry.PanelSpecs(),
    PanelRegistry.ConverterSpecs,
    Types.isAssignableTo
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

const getTypeHandlerStacks = (currentType: Types.Type) => {
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
  Types.Type,
  Panel.PanelSpec,
  Panel.PanelConvertSpec
>;

// This function determines the recommendation order!
function scoreHandlerStack(type: Types.Type, hs: PanelStack) {
  const sidAndName = PanelLib.getStackIdAndName(hs);
  let scoreHs = 0;
  if (sidAndName.id.startsWith(PanelTableMergeSpec.id)) {
    scoreHs += 10;
  }

  if (
    sidAndName.id.startsWith('row') &&
    !Types.isMediaTypeLike(
      Types.listObjectType(Types.nullableTaggableValue(type))
    )
  ) {
    scoreHs -= 5;
  }

  if (sidAndName.id.indexOf('row.row') > -1) {
    scoreHs -= 10;
  }

  // Table catches all lists, put it behind row for non-dict types
  if (
    (hs.id === 'table' || hs.id === 'plot') &&
    Types.isListLike(type) &&
    !Types.isTypedDictLike(
      Types.nullableTaggableValue(
        Types.listObjectType(Types.nullableTaggableValue(type))
      )
    )
  ) {
    scoreHs -= 10;
  }

  // void is only assignable to any, use this to detect very permissive
  // panels and give them a low score.
  if (
    (Types.isAssignableTo2('invalid', hs.inputType) ||
      Types.isAssignableTo2(Types.list('invalid'), hs.inputType)) &&
    hs.id !== 'table' &&
    !sidAndName.id.endsWith('plot')
  ) {
    scoreHs -= 15;
  }
  if (sidAndName.id.includes('any-obj')) {
    scoreHs -= 50;
  }
  return scoreHs;
}

// Get the panels available for a given type. If a panelId is already
// chosen, pass it as the second argument. The curPanelId will match
// panelId if it is available, otherwise it will revert to the first
// available panel.
interface GetPanelStacksForTypeOpts {
  excludeTable?: boolean;
  excludePlot?: boolean;
  excludeMultiTable?: boolean;
  modelRegistryEnabled?: boolean;
}
export function getPanelStacksForType(
  type: Types.Type,
  panelId: string | undefined,
  opts: GetPanelStacksForTypeOpts = {}
): {
  curPanelId: string | undefined;
  stackIds: Array<{id: string; displayName: string}>;
  handler: PanelStack | undefined;
} {
  if (panelId != null && panelId !== '') {
    // If its a non-input panel its inputType will be 'invalid'. Just return it directly.
    const curStack = panelSpecById(panelId);
    if (curStack.inputType === 'invalid') {
      return {
        curPanelId: panelId,
        stackIds: [PanelLib.getStackIdAndName(curStack)],
        handler: curStack,
      };
    }
  }
  let handlerStacks = type === 'invalid' ? [] : getTypeHandlerStacks(type);
  if (opts.excludeTable) {
    handlerStacks = handlerStacks.filter(
      hs => !PanelLib.getStackIdAndName(hs).id.endsWith('table')
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
  if (!opts.modelRegistryEnabled) {
    handlerStacks = handlerStacks.filter(
      hs =>
        PanelLib.getStackIdAndName(hs).id.indexOf('artifact-collection') === -1
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

  const stackIds = handlerStacks.map(PanelLib.getStackIdAndName);
  const configuredStackIndex = stackIds.findIndex(si => si.id === panelId);
  let backupConfiguredStackIndex = -1;
  // If there is not an exact match...
  if (panelId != null) {
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

  const curPanelId =
    configuredStackIndex !== -1
      ? stackIds[configuredStackIndex].id
      : backupConfiguredStackIndex !== -1
      ? stackIds[backupConfiguredStackIndex].id
      : stackIds.length > 0 && stackIds[0].id !== 'layout-container'
      ? stackIds[0].id
      : undefined;
  const actualStackIndex = stackIds.findIndex(si => si.id === curPanelId);
  const handler =
    actualStackIndex !== -1 ? handlerStacks[actualStackIndex] : undefined;
  return {curPanelId, stackIds, handler};
}

export function usePanelStacksForType(
  type: Types.Type,
  panelId: string | undefined,
  opts: GetPanelStacksForTypeOpts = {}
) {
  // Deep memo this so the caller doesn't have to worry about ref-equality
  opts = useDeepMemo(opts);
  const {'model-registry': modelRegistryEnabled} = useContext(WeaveAppContext);
  return useMemo(
    () =>
      getPanelStacksForType(type, panelId, {
        ...opts,
        excludePlot: opts.excludePlot,
        excludeMultiTable: opts.excludeMultiTable || opts.excludeTable,
        modelRegistryEnabled,
      }),
    [type, panelId, opts, modelRegistryEnabled]
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
export function getPanelStackDims<C, T extends Types.Type>(
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
  const panel = PanelRegistry.ConverterSpecs.find(p => p.id === panelId);
  if (panel == null) {
    return false;
  }
  return (panel as any).equivalentTransform != null;
}

export function getTransformPanel(panelId: string) {
  const panel = PanelRegistry.ConverterSpecs.find(p => p.id === panelId);
  if (panel == null) {
    return undefined;
  }
  return panel as unknown as Panel.PanelSpec;
}

export function panelSpecById(panelId: string) {
  const panel = PanelRegistry.PanelSpecs().find(p => p.id === panelId);
  if (panel == null) {
    throw Error('unknown panelId: ' + panelId);
  }
  return panel;
}
