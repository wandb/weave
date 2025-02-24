import {
  BoundingBoxSliderControl,
  LineStyle,
} from '@wandb/weave/common/components/MediaCard';
import {colorFromName, colorN, ROBIN16} from '@wandb/weave/common/util/colors';
import {ImageType, nullableTaggableStrip, Type} from '@wandb/weave/core';
import * as _ from 'lodash';
import {useMemo} from 'react';

export interface OverlayControls {
  [overlayID: string]: OverlayState;
}

export interface OverlayClassState {
  opacity: number;
  disabled: boolean;
}

export interface BaseOverlayState {
  type: ControlType;
  name: string;
  disabled: boolean;
  classSearch: string;
  classSetID: string;
  classOverlayStates: {[classID: string]: OverlayClassState};
  hideLabels?: boolean;
}

export interface BoxControlState extends BaseOverlayState {
  type: 'box';
  lineStyle?: LineStyle;
}

export interface MaskControlState extends BaseOverlayState {
  type: 'mask';
  hideImage?: boolean;
}

export interface BoxSliderState {
  [valueName: string]: BoundingBoxSliderControl;
}

export type OverlayState = BoxControlState | MaskControlState;
export type ControlType = OverlayState['type'];

export type UpdateControl = <T extends BaseOverlayState>(
  newControl: Partial<T>
) => void;

export interface ClassState {
  color: string;
  name: string;
}

export interface ClassSetState {
  classes: {
    [classID: string]: ClassState;
  };
}

export interface ClassSetControls {
  [classSetID: string]: ClassSetState;
}

function createBaseControls(
  name: string,
  classSetID: string,
  classSet: ClassSetState
): Omit<BaseOverlayState, 'type'> {
  const classStates = Object.fromEntries(
    Object.keys(classSet.classes).map(classID => [
      classID,
      {opacity: 1, disabled: false},
    ])
  );
  return {
    name,
    classSetID,
    classOverlayStates: classStates,
    classSearch: '',
    disabled: false,
  };
}

export function createMaskControls(
  ...args: Parameters<typeof createBaseControls>
): MaskControlState {
  return {...createBaseControls(...args), type: 'mask'};
}

export function createBoxControls(
  ...args: Parameters<typeof createBaseControls>
): BoxControlState {
  return {
    ...createBaseControls(...args),
    type: 'box',
    lineStyle: 'line',
  };
}

const defaultClassSetID = 'default';

export const useImageControls = (
  inputType: Type,
  currentControls?: OverlayControls
) => {
  const usableType = useMemo(() => {
    return nullableTaggableStrip(inputType) as ImageType;
  }, [inputType]);

  // Images now only have a single class set (the default one) as the
  // classes from all layers have been merged in the type system
  const classSets = useMemo(() => {
    const classSet = _.mapValues(usableType.classMap ?? {}, (value, key) => {
      const keyNOrNan = parseInt(key, 10);
      const color = isNaN(keyNOrNan)
        ? colorFromName(key)
        : colorN(keyNOrNan, ROBIN16);
      return {color, name: value};
    }) as ClassSetState['classes'];
    return {
      [defaultClassSetID]: {classes: classSet},
    } as ClassSetControls;
  }, [usableType]);

  const maskControls: {[key: string]: MaskControlState} = useMemo(() => {
    const maskLayers = usableType.maskLayers ?? {};
    return _.fromPairs(
      _.keys(maskLayers).map(maskId => {
        const prefixedId = 'mask-' + maskId;
        if (currentControls?.[prefixedId] != null) {
          return [prefixedId, currentControls[prefixedId] as MaskControlState];
        }
        const classSubset = _.pick(
          classSets[defaultClassSetID].classes,
          ...maskLayers[maskId]
        );
        const newControl: MaskControlState = createMaskControls(
          prefixedId,
          defaultClassSetID,
          {classes: classSubset}
        );
        return [prefixedId, newControl];
      })
    );
  }, [usableType, classSets, currentControls]);

  const boxControls: {[key: string]: BoxControlState} = useMemo(() => {
    const boxLayers = usableType.boxLayers ?? {};
    return _.fromPairs(
      _.keys(boxLayers).map(boxId => {
        const prefixedId = 'box-' + boxId;
        if (currentControls?.[prefixedId] != null) {
          return [prefixedId, currentControls[prefixedId] as BoxControlState];
        }
        const classSubset = _.pick(
          classSets[defaultClassSetID].classes,
          ...boxLayers[boxId]
        );
        const newControl: BoxControlState = createBoxControls(
          prefixedId,
          defaultClassSetID,
          {classes: classSubset}
        );
        return [prefixedId, newControl];
      })
    );
  }, [usableType, classSets, currentControls]);

  const controls = useMemo(() => {
    return {
      ...maskControls,
      ...boxControls,
    };
  }, [maskControls, boxControls]);

  return {
    maskControls,
    boxControls,
    controls,
    classSets,
  };
};
