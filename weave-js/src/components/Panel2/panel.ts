import * as TypeHelpers from '@wandb/weave/core';
import * as Types from '@wandb/weave/core';
import * as GraphTypes from '@wandb/weave/core';
import * as Graph from '@wandb/weave/core';
import * as Editing from '@wandb/weave/core';
import {Client} from '@wandb/weave/core';
import * as React from 'react';

import {ClassSetControls} from './controlsImage';
import * as PanelLib from './panellib/libpanel';
import * as TSTypeWithPath from './tsTypeWithPath';

export interface PanelContext {
  classSets?: ClassSetControls;

  // TODO: Get rid of path. It's used by PanelDir. Should we have an "updateInput" ?
  path?: string[];
}

export type UpdateContext = (partialContext: Partial<PanelContext>) => void;

// Panel input is a TSTypeWithPath, which for all input types other than
// Dict, resolves to a {path: QueryPathSingle, value: TSType} object. For
// Dict, we enforce that a path is included with each incoming value of the dict.
// This means that each incoming value, or series of values in the case
// of a dict, must be accompanied by a QueryPathSingle. QueryPathSingle
// can be converted to a query, which can be used to refetch the incoming
// value or values.

// This is the external version of PanelInput, ie, the type the caller
// must conform to when instantiating panels.
export type PanelInput = TSTypeWithPath.PathObjOrDictWithPath<any>;

// This is the Panel's input specifically typed for the given panel. This
// is the type the panel's author will work with when writing code inside
// the panel.
type PanelInputInternal<I extends Types.Type> =
  TSTypeWithPath.TypeToTSTypeWithPath<I>;

export type PanelProps<I extends Types.Type, C = any> = PanelLib.PanelProps<
  PanelInputInternal<I>,
  C,
  PanelContext
>;

export type PanelSpec<C = any> = PanelLib.PanelSpec<
  PanelContext,
  C,
  Types.Type
>;

export type PanelConverterProps<C = any> = PanelLib.PanelConverterProps<
  PanelContext,
  C,
  Types.Type
>;
export type PanelConvertSpec<C = any> = PanelLib.PanelConvertSpec<
  PanelContext,
  C,
  Types.Type
>;

export type PanelConvertWithChildSpec<C = any> =
  PanelLib.PanelConvertWithChildSpec<PanelContext, C, Types.Type>;

export type PanelSpecNode<C = any> = PanelLib.PanelSpecNode<
  PanelContext,
  C,
  Types.Type
>;

export function toConvertSpec(panelSpec: PanelSpec): PanelConvertSpec {
  const outputTypeFn = panelSpec.outputType;
  if (outputTypeFn == null) {
    throw new Error('Invalid panel spec: missing outputType');
  }
  return {
    id: panelSpec.id,
    displayName: panelSpec.displayName,
    ConfigComponent: panelSpec.ConfigComponent,
    Component: panelSpec.Component,
    defaultFixedSize: panelSpec.defaultFixedSize,
    canFullscreen: panelSpec.canFullscreen,
    equivalentTransform: panelSpec.equivalentTransform,
    isValid: panelSpec.isValid,
    convert: (inputType: Types.Type) => {
      if (!TypeHelpers.isAssignableTo(inputType, panelSpec.inputType)) {
        return null;
      }
      return outputTypeFn(inputType);
    },
  } as any;
}

export type ConfiguredTransform<
  I extends Editing.EditingNode,
  O extends GraphTypes.NodeOrVoidNode
> = (
  inputNode: I,
  config: any,
  refineNode: GraphTypes.ExpansionRefineNodeCallback,
  client: Client
) => Promise<O>;

export function registerPanelFunction(
  panelId: string,
  inputType: Types.Type,
  configuredTransform: ConfiguredTransform<
    Editing.EditingNode,
    GraphTypes.NodeOrVoidNode
  >
) {
  Graph.registerGeneratedWeaveOp({
    name: panelIdToPanelOpName(panelId),
    inputTypes: {input: inputType, config: 'any'},
    outputType: 'any',
    expansionFn: (inputs, refineNode, client) => {
      const {input, config} = inputs;
      if (config.nodeType !== 'const') {
        throw new Error('panel config must be const node');
      }
      return configuredTransform(input, config.val, refineNode, client) as any;
    },
  });
}

const PANEL_OPNAME_PREFIX = 'panel-';

export function panelIdToPanelOpName(panelId: string): string {
  return PANEL_OPNAME_PREFIX + panelId;
}

export function isPanelOpName(opName: string): boolean {
  return opName.startsWith(PANEL_OPNAME_PREFIX);
}

export function panelOpNameToPanelId(opName: string): string {
  if (!isPanelOpName(opName)) {
    throw new Error('not a panel op:' + opName);
  }
  return opName.slice(PANEL_OPNAME_PREFIX.length);
}

export function useConfig<T extends {}>(
  initialConfig: T = {} as T
): [T, (update: Partial<T>) => void] {
  const [config, setConfig] = React.useState<T>(initialConfig);
  const updateConfig = React.useCallback(
    (update: Partial<T>) => {
      setConfig(curConfig => ({
        ...curConfig,
        ...update,
      }));
    },
    [setConfig]
  );

  return [config, updateConfig];
}

export function useConfigChild<T extends {[key: string]: any}>(
  key: string,
  config: T | undefined,
  updateConfig: (update: Partial<T>) => void,
  defaultValue?: any
) {
  const childConfig = React.useMemo(
    () => (config != null ? config[key] ?? defaultValue : defaultValue),
    [key, defaultValue, config]
  );
  const updateChildConfig = React.useCallback(
    (update: Partial<typeof childConfig>) => {
      const newChild = {
        ...childConfig,
        ...update,
      };
      updateConfig({[key]: newChild} as any);
    },
    [childConfig, key, updateConfig]
  );

  return React.useMemo(
    () => ({
      config: childConfig,
      updateConfig: updateChildConfig,
    }),
    [childConfig, updateChildConfig]
  );
}

export const dummyProps = {
  config: undefined,
  updateConfig: (...args: any[]) => {},
  context: {},
  updateContext: (...args: any[]) => {},
};
