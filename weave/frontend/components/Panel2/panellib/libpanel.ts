// Generic parameters:
// Globals
//   X: context
//   T: libtypes type
// Panel specific
//   C: config type
//   I: input type
import * as Types from '@wandb/cg/browser/model/types';
import * as CGTypes from '@wandb/cg/browser/types';
import {ConfiguredTransform} from '../panel';

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
    partialConfig: C extends undefined ? undefined : Partial<C>
  ): void;

  updateInput?(newInput: Partial<I>): void;
}

export type PanelProps<I, C, X> = PanelPropsInternal<I, C, X>;

interface Dimensions {
  width: number | undefined;
  height: number | undefined;
}
export interface PanelSpec<X, C, T extends Types.Type> {
  id: string;
  displayName?: string;
  ConfigComponent?: React.ComponentType<PanelPropsInternal<any, C, X>>;
  Component: React.ComponentType<PanelPropsInternal<any, C, X>>;

  inputType: T;

  outputType?: (inputType: T) => Types.Type;

  equivalentTransform?: ConfiguredTransform<
    CGTypes.EditingNode<T>,
    Types.NodeOrVoidNode
  >;

  /**
   * Panels with `canFullscreen` will expand or shrink to fill the available vertical
   * space in their parent, and then restrict content from overflowing.
   * Otherwise, panels will expand vertically based on the size of their content.
   */
  canFullscreen?: boolean;

  defaultFixedSize?: Dimensions | ((config: C) => Dimensions);
}

export type PanelConverterProps<
  X,
  C,
  T extends Types.Type
> = PanelPropsInternal<any, C, X> & {
  child: PanelSpecNode<X, C, T>;
  inputType: T;
};

export interface PanelConvertSpec<X, C, T extends Types.Type> {
  id: string;
  displayName?: string;
  ConfigComponent?: React.ComponentType<PanelConverterProps<X, C, T>>;
  Component: React.ComponentType<PanelConverterProps<X, C, T>>;
  canFullscreen?: boolean;
  equivalentTransform?: ConfiguredTransform<
    CGTypes.EditingNode<T>,
    Types.NodeOrVoidNode
  >;
  convert(inputType: T): T | null;
  defaultFixedSize?(childDims: Dimensions, type: T, config: C): Dimensions;
}

export type PanelConvertWithChildSpec<
  X,
  C,
  T extends Types.Type
> = PanelConvertSpec<X, C, T> & {
  child: any;
  inputType: T;
  convert(inputType: T): T | null;
};

export type PanelSpecNode<X, C, T extends Types.Type> =
  | PanelSpec<X, C, T>
  | PanelConvertWithChildSpec<X, C, T>;

export function isWithChild<X, C, T extends Types.Type>(
  spec: PanelSpecNode<X, C, T>
): spec is PanelConvertWithChildSpec<X, C, T> {
  return (spec as any).child != null;
}

export function isTransform<X, C, T extends Types.Type>(
  spec: PanelSpecNode<X, C, T>
): boolean {
  return (spec as any).equivalentTransform != null;
}

export function getDisplayName<X, C, T extends Types.Type>(
  panel: PanelSpecNode<X, C, T>
): string {
  if (panel.displayName != null) {
    return panel.displayName;
  }
  const words = panel.id.split('-');
  return words.map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('');
}
export function getStackIdAndName<X, C, T extends Types.Type>(
  panel: PanelSpecNode<X, C, T>
): {id: string; displayName: string} {
  if (isWithChild(panel)) {
    const {id, displayName} = getStackIdAndName(panel.child);
    return {
      id: panel.id + '.' + id,
      displayName: getDisplayName(panel) + ': ' + displayName,
    };
  }
  return {id: panel.id, displayName: getDisplayName(panel)};
}
