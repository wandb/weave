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

export type MaskClassLabels = {
  key: string;
  type: string;
  value: {[key: string]: string};
};

const toClassValue = (className: string, classKey: string) => {
  const keyNOrNan = parseInt(classKey, 10);
  const color = isNaN(keyNOrNan)
    ? colorFromName(classKey)
    : colorN(keyNOrNan, ROBIN16);
  return {color, name: className};
};

export const useImageControls = (
  inputType: Type,
  currentControls?: OverlayControls,
  maskClassLabels?: {[key: string]: MaskClassLabels}
) => {
  const usableType = useMemo(() => {
    return nullableTaggableStrip(inputType) as ImageType;
  }, [inputType]);

  const classSets = useMemo(() => {
    const defaultClassSet = _.mapValues(
      usableType.classMap ?? {},
      (className, classKey) => toClassValue(className, classKey)
    ) as ClassSetState['classes'];

    const classSetsFromLabels = Object.entries(maskClassLabels ?? {}).reduce(
      (acc, [maskKey, mask]) => {
        const controlId = `mask-${maskKey.replace(
          'image_wandb_delimeter_',
          ''
        )}`;
        acc[controlId] = {
          classes: _.mapValues(mask.value, (labelName, labelKey) =>
            toClassValue(labelName, labelKey)
          ),
        };
        return acc;
      },
      {} as ClassSetControls
    );

    return {
      [defaultClassSetID]: {classes: defaultClassSet},
      ...classSetsFromLabels,
    } as ClassSetControls;
  }, [usableType, maskClassLabels]);

  const maskControls: {[key: string]: MaskControlState} = useMemo(() => {
    const maskLayers = usableType.maskLayers ?? {};
    return _.fromPairs(
      _.keys(maskLayers).map(maskId => {
        const prefixedId = 'mask-' + maskId;
        if (
          currentControls &&
          _.findKey(
            currentControls,
            control => control.classSetID === prefixedId
          )
        ) {
          return [prefixedId, currentControls[prefixedId] as MaskControlState];
        }
        let classSetId = defaultClassSetID;
        if (prefixedId in classSets) {
          classSetId = prefixedId;
        }
        const classSet = classSets[classSetId];
        const classSubset = _.pick(classSet.classes, ...maskLayers[maskId]);
        const newControl: MaskControlState = createMaskControls(
          prefixedId,
          classSetId,
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
