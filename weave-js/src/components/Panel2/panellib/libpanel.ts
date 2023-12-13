import {
  EditingNode,
  NodeOrVoidNode,
  Stack,
  Type,
  Weave,
} from '@wandb/weave/core';

import {IconName} from '../../Icon';
import {ConfiguredTransform} from '../panel';
import {PanelCategory} from './types';

// Generic parameters:
// Globals
//   X: context
//   T: libtypes type
// Panel specific
//   C: config type
//   I: input type

interface PanelPropsInternal<I, C, X> {
  input: I;

  // No longer needed. TODO: remove
  loading?: boolean;
  context: X;
  config?: C;
  configMode?: boolean;
  updateContext(partialContext: Partial<X>): void;

  // lazily-imported components with no config make ts complain if we don't do
  // this
  updateConfig(
    partialConfig?: C extends undefined ? undefined : Partial<C>
  ): void;
  updateConfig2?(change: (oldConfig: C) => Partial<C>): void;

  // For newInput, child can pass either:
  //
  // - A Weave function of a variable 'input'. In that case parent is responsible
  //   for applying the function such that child's next render will have the function
  //   applied to its input
  // - A Node with no variables that can be evaluated. Parent will pass this up the
  //   the chain until root is reached, at which point the root expression will be replaced.
  //
  // Shawn: I am not positive these are the exact patterns we want for achieving this, but
  //   lets go with it and adjust later.
  updateInput?(newInput: Partial<I>): void;
}

export type PanelProps<I, C, X> = PanelPropsInternal<I, C, X>;

interface Dimensions {
  width: number | undefined;
  height: number | undefined;
}

export interface PanelSpec<X, C, T extends Type> {
  id: string;
  hidden?: boolean;
  displayName?: string;

  // An icon that will be associated with this panel type.
  // Used in panel type selector, outline, etc.
  icon?: IconName;

  category?: PanelCategory;

  // Provide initial config for panel. This is called once when the panel
  // is first created.
  initialize?: (
    weave: Weave,
    inputType: NodeOrVoidNode<T>,
    stack: Stack
  ) => Promise<C> | C;
  ConfigComponent?: React.ComponentType<PanelPropsInternal<any, C, X>>;
  Component: React.ComponentType<PanelPropsInternal<any, C, X>>;
  inputType: T;

  outputType?: (inputType: T) => Type;

  equivalentTransform?: ConfiguredTransform<EditingNode<T>, NodeOrVoidNode>;

  /**
   * Panels with `canFullscreen` will expand or shrink to fill the available vertical
   * space in their parent, and then restrict content from overflowing.
   * Otherwise, panels will expand vertically based on the size of their content.
   */
  canFullscreen?: boolean;

  defaultFixedSize?: Dimensions | ((config: C) => Dimensions);
  isValid?: (config: any) => boolean;

  // `shouldSuggest` is a function that returns true if the panel should be
  // suggested. If `shouldSuggest` is not provided, the panel will be suggested
  // if it is not hidden. This should only be used in very rare edge cases where
  // the type system is insufficient
  shouldSuggest?: (inputType: T) => boolean;
}

export type PanelConverterProps<X, C, T extends Type> = PanelPropsInternal<
  any,
  C,
  X
> & {
  child: PanelSpecNode<X, C, T>;
  inputType: T;
};

export interface PanelConvertSpec<X, C, T extends Type> {
  id: string;
  hidden?: boolean;
  displayName?: string;
  ConfigComponent?: React.ComponentType<PanelConverterProps<X, C, T>>;
  Component: React.ComponentType<PanelConverterProps<X, C, T>>;
  canFullscreen?: boolean;
  equivalentTransform?: ConfiguredTransform<EditingNode<T>, NodeOrVoidNode>;
  isValid?: (config: any) => boolean;
  convert(inputType: T): T | null;
  defaultFixedSize?(childDims: Dimensions, type: T, config: C): Dimensions;
}

export type PanelConvertWithChildSpec<X, C, T extends Type> = PanelConvertSpec<
  X,
  C,
  T
> & {
  child: any;
  inputType: T;
  convert(inputType: T): T | null;
};

export type PanelSpecNode<X, C, T extends Type> =
  | PanelSpec<X, C, T>
  | PanelConvertWithChildSpec<X, C, T>;

export function isWithChild<X, C, T extends Type>(
  spec: PanelSpecNode<X, C, T>
): spec is PanelConvertWithChildSpec<X, C, T> {
  return (spec as any).child != null;
}

export function isTransform<X, C, T extends Type>(
  spec: PanelSpecNode<X, C, T>
): boolean {
  return (spec as any).equivalentTransform != null;
}

export function getDisplayName<X, C, T extends Type>(
  panel: PanelSpecNode<X, C, T>
): string {
  if (panel.displayName != null) {
    return panel.displayName;
  }
  const words = panel.id.split('-');
  return words.map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('');
}

function shouldHidePanelInStack(panelName: string) {
  return ['Maybe'].includes(panelName);
}

export function getStackIdAndName<X, C, T extends Type>(
  panel: PanelSpecNode<X, C, T>
): {id: string; displayName: string} {
  const ourDisplayName = getDisplayName(panel);
  if (isWithChild(panel)) {
    const {id, displayName: childDisplayName} = getStackIdAndName(panel.child);
    let displayName = ourDisplayName + ' ▸ ' + childDisplayName;

    // Some special cosmetic cases. This may end up being too confusing,
    // but trying it out for now.
    if (shouldHidePanelInStack(ourDisplayName)) {
      displayName = childDisplayName;
    } else if (
      ourDisplayName === '2D Projection' &&
      childDisplayName === 'Plot'
    ) {
      displayName = '2D Projection';
    } else if (
      ourDisplayName === 'Run Tables' &&
      childDisplayName === 'Paginated Tables'
    ) {
      displayName = 'Run Tables';
    } else if (
      ourDisplayName === 'Run Tables' &&
      childDisplayName === 'Paginated Plots'
    ) {
      displayName = 'Run Tables  ▸  Plots';
    } else if (
      ourDisplayName === 'Run Tables' &&
      childDisplayName === 'Paginated 2D Projection'
    ) {
      displayName = 'Run Tables  ▸  2D Projections';
    } else if (
      ourDisplayName === 'Run Tables' &&
      childDisplayName === 'Combined Table'
    ) {
      displayName = 'Run Tables  ▸  Combined';
    } else if (
      ourDisplayName === 'Combined Table' &&
      childDisplayName === 'Table'
    ) {
      displayName = 'Combined Table';
    } else if (
      ourDisplayName === 'Combined Table' &&
      childDisplayName === 'Plot'
    ) {
      displayName = 'Combined Plot';
    } else if (
      ourDisplayName === 'Combined Table' &&
      childDisplayName === '2D Projection'
    ) {
      displayName = 'Combined 2D Projection';
    } else if (ourDisplayName === 'List' && childDisplayName === 'Table') {
      displayName = 'Paginated Tables';
    } else if (ourDisplayName === 'List' && childDisplayName === 'Plot') {
      displayName = 'Paginated Plots';
    } else if (
      ourDisplayName === 'List' &&
      childDisplayName === '2D Projection'
    ) {
      displayName = 'Paginated 2D Projection';
    }

    return {
      id: panel.id + '.' + id,
      displayName,
    };
  }
  return {id: panel.id, displayName: ourDisplayName};
}
