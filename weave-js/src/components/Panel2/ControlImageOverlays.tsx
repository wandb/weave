import {WBIcon} from '@wandb/ui';
import HelpPopup from '@wandb/weave/common/components/elements/HelpPopup';
import {BoundingBoxSliderControl} from '@wandb/weave/common/components/MediaCard';
import {ShowMoreContainer} from '@wandb/weave/common/components/showMoreContainer';
import {BoundingBox2D, LayoutType} from '@wandb/weave/common/types/media';
import {fuzzyMatchRegex} from '@wandb/weave/common/util/fuzzyMatch';
import {CompareOp} from '@wandb/weave/common/util/ops';
import classNames from 'classnames';
import * as _ from 'lodash';
import React, {useMemo} from 'react';
import {Button, ButtonGroup} from 'semantic-ui-react';

import {ControlsBox} from './ControlBox';
import * as S from './ControlImageOverlays.styles';
import {ControlsMask} from './ControlMask';
import * as Controls from './controlsImage';
import {ClassSetControls, ClassSetState} from './controlsImage';
import {
  BoxConfidenceControl,
  ClassToggle,
  ClassToggleWithSlider,
  ControlTitle,
  LabelToggle,
  SearchInput,
} from './ControlsUtil';
import {
  DEFAULT_ALL_MASK_CONTROL,
  DEFAULT_TILE_LAYOUT,
} from './ImageWithOverlays';

type BoxSliderControlsProps = {
  boxes: {[boxGroup: string]: BoundingBox2D[]};
  sliders?: Controls.BoxSliderState;
  updateSliders(update: Controls.BoxSliderState): void;
};

export const BoxSliderControls: React.FC<BoxSliderControlsProps> = ({
  boxes,
  sliders,
  updateSliders,
}) => {
  const sliderRanges = useMemo(() => {
    const ranges = {} as {
      [key: string]: {min: number; max: number};
    };
    for (const bs of Object.values(boxes)) {
      for (const b of bs) {
        for (const s of Object.entries(b.scores ?? {})) {
          const [scoreName, scoreValue] = s;
          const oldRange = ranges[scoreName];
          ranges[scoreName] =
            oldRange == null
              ? {min: scoreValue, max: scoreValue}
              : {
                  min: Math.min(oldRange.min, scoreValue),
                  max: Math.max(oldRange.max, scoreValue),
                };
        }
      }
    }
    return ranges;
  }, [boxes]);

  return (
    <div className="control-popup__item">
      {Object.entries(sliderRanges).map(([property, range]) => {
        const slider = sliders?.[property] ?? {
          comparator: 'gte',
          value: range.min,
        };
        const updateSlider = (newSlider: Partial<BoundingBoxSliderControl>) => {
          updateSliders({[property]: {...slider, ...newSlider}});
        };

        const onDisabledChange = () =>
          updateSlider({disabled: !slider.disabled});
        const onOperatorChange = (op: CompareOp) =>
          updateSlider({comparator: op});
        const onSliderChange = (v: number) => updateSlider({value: v});
        return (
          <BoxConfidenceControl
            key={property}
            name={property}
            {...slider}
            slideRange={range}
            onDisableChange={onDisabledChange}
            onOperatorChange={onOperatorChange}
            onSliderChange={onSliderChange}
          />
        );
      })}
    </div>
  );
};

type ClassTogglesProps = {
  type: 'mask' | 'box';
  filterString?: string;
  classStates: {[classID: string]: Controls.OverlayClassState};
  classSet: ClassSetState;
  updateControl: Controls.UpdateControl;
};

export const ClassToggles: React.FC<ClassTogglesProps> = ({
  type,
  filterString = '',
  classStates,
  classSet,
  updateControl,
}) => {
  const filterRegex = useMemo(() => {
    return fuzzyMatchRegex(filterString);
  }, [filterString]);

  const classMatchesFilter = (classId: string) => {
    const name = classSet.classes[classId]?.name;
    if (name != null) {
      return String(name).match(filterRegex);
    }
    return null;
  };

  const classIds = Object.keys(classStates).filter(classMatchesFilter);
  return (
    <ShowMoreContainer>
      {classIds.map(classId => {
        const classState = classStates[classId];
        const classInfo = classSet.classes[classId];
        const {disabled, opacity} = classState;

        const toggleClassVisibility = () =>
          updateControl({
            classOverlayStates: {
              ...classStates,
              [classId]: {
                ...classState,
                disabled: !disabled,
              },
            },
          });

        const setClassOpacity = (o: number) =>
          updateControl({
            classOverlayStates: {
              ...classStates,
              [classId]: {...classState, opacity: o},
            },
          });

        return type === 'mask' ? (
          <ClassToggleWithSlider
            key={classId}
            disabled={disabled}
            name={classInfo.name}
            color={classInfo.color}
            opacity={opacity}
            onOpacityChange={setClassOpacity}
            onClick={toggleClassVisibility}
          />
        ) : (
          <ClassToggle
            key={classId}
            disabled={disabled}
            name={classInfo.name}
            color={classInfo.color}
            onClick={toggleClassVisibility}
          />
        );
      })}
    </ShowMoreContainer>
  );
};

type TileLayoutButtonsProps = {
  tileLayout?: LayoutType;
  setLayoutType: (l: LayoutType) => void;
  maskCount: number;
};

const TileLayoutButtons: React.FC<TileLayoutButtonsProps> = ({
  tileLayout = 'ALL_STACKED',
  setLayoutType,
  maskCount,
}) => {
  return (
    <div style={{margin: 24}}>
      <ButtonGroup>
        <Button
          size="tiny"
          icon
          className={classNames({
            'action-button--active': tileLayout === 'ALL_STACKED',
          })}
          onClick={() => setLayoutType('ALL_STACKED')}>
          <WBIcon name="overlay-stack" />
        </Button>
        <Button
          size="tiny"
          icon
          className={classNames({
            'action-button--active': tileLayout === 'MASKS_NEXT_TO_IMAGE',
          })}
          onClick={() => setLayoutType('MASKS_NEXT_TO_IMAGE')}>
          <WBIcon name={'overlay-2-column'} />
        </Button>
        {maskCount > 1 && (
          <Button
            size="tiny"
            icon
            className={classNames({
              'action-button--active': tileLayout === 'ALL_SPLIT',
            })}
            onClick={() => setLayoutType('ALL_SPLIT')}>
            <WBIcon name="overlay-3-column" />
          </Button>
        )}
      </ButtonGroup>
      <span style={{marginLeft: -5}}>
        <HelpPopup helpText="Toggle the layout of the masks between: a stack of image and masks, masks adjacent to image, and all spread out"></HelpPopup>
      </span>
    </div>
  );
};

interface ClassStates {
  [classID: string]: Controls.OverlayClassState;
}

export interface ControlsImageOverlaysControls {
  hideImage?: boolean;
  tileLayout?: LayoutType;
  boxSliders?: Controls.BoxSliderState;
  overlayControls?: Controls.OverlayControls;
}

type ControlsImageOverlaysProps = {
  boxes?: {
    [boxGroup: string]: BoundingBox2D[];
  };
  controls?: ControlsImageOverlaysControls;
  classSets?: ClassSetControls;
  updateControls(partialConfig: Partial<ControlsImageOverlaysControls>): void;
};

export const ControlsImageOverlays: React.FC<
  ControlsImageOverlaysProps
> = props => {
  const {controls, classSets, updateControls, boxes} = props;
  const {
    overlayControls,
    boxSliders,
    tileLayout = DEFAULT_TILE_LAYOUT,
  } = controls ?? {};

  const setControls = (controlId: string, newControl: Controls.OverlayState) =>
    updateControls({
      ...controls,
      overlayControls: {
        ...controls?.overlayControls,
        [controlId]: newControl,
      },
    });

  const setLayoutType = (layout: LayoutType) =>
    updateControls({...controls, tileLayout: layout});

  if (controls == null || classSets == null) {
    return <div></div>;
  }

  const masks = Object.values(overlayControls ?? []).filter(
    t => t.type === 'mask'
  );

  return (
    <div>
      {boxes && (
        <BoxSliderControls
          boxes={boxes}
          updateSliders={sliders =>
            updateControls({
              ...controls,
              boxSliders: {...(controls?.boxSliders ?? {}), ...sliders},
            })
          }
          sliders={boxSliders}
        />
      )}
      {masks.length > 0 && (
        <TileLayoutButtons
          tileLayout={tileLayout}
          setLayoutType={setLayoutType}
          maskCount={masks.length}
        />
      )}
      {_.map(overlayControls, (control, controlId) => {
        const {
          type,
          name,
          classSetID,
          classOverlayStates: classStates,
          classSearch,
        } = control;
        const classSet = classSets[classSetID];

        if (classSet == null) {
          return null;
        }

        const allClass =
          control.classOverlayStates?.all ?? DEFAULT_ALL_MASK_CONTROL;

        const updateControl: Controls.UpdateControl = newControl => {
          const mergedControl = {...control, ...newControl};
          setControls(controlId, mergedControl);
        };

        const toggleControlVisibility = () => {
          updateControl({
            classOverlayStates: {
              ...control.classOverlayStates,
              all: {
                ...allClass,
                disabled: !allClass.disabled,
              },
            },
          });
        };

        const setClassSearch = (newClassSearch: string) => {
          updateControl({classSearch: newClassSearch});
        };

        const setAllClasses = (disabled: boolean) => {
          const newClassState: ClassStates = {};
          const classes = Object.entries(control.classOverlayStates);
          for (const [className, state] of classes) {
            if (className === 'all') {
              continue;
            }
            newClassState[className] = {...state, disabled};
          }
          updateControl({
            classOverlayStates: {...classStates, ...newClassState},
          });
        };

        const setHideLabels = (hide: boolean) => {
          updateControl({
            hideLabels: hide,
          });
        };

        return (
          <S.Wrapper key={controlId}>
            <S.Header>
              <S.VisibilityToggleWrapper>
                <ClassToggle
                  name="all"
                  disabled={allClass.disabled}
                  onClick={toggleControlVisibility}
                />
              </S.VisibilityToggleWrapper>
              <S.TitleWrapper>
                <ControlTitle>
                  {name} ({type})
                </ControlTitle>
              </S.TitleWrapper>
              {type === 'box' && (
                <S.LabelToggleWrapper>
                  <LabelToggle
                    disabled={control.hideLabels ?? false}
                    onClick={() => setHideLabels(!control.hideLabels)}>
                    Labels
                  </LabelToggle>
                </S.LabelToggleWrapper>
              )}

              <S.SearchWrapper>
                <SearchInput value={classSearch} onChange={setClassSearch} />
              </S.SearchWrapper>
              <S.ActionsWrapper>
                {type === 'box' && (
                  <>
                    <ControlsBox
                      box={control as Controls.BoxControlState}
                      updateBox={updateControl}
                    />
                  </>
                )}
                {type === 'mask' && (
                  <ControlsMask
                    controls={controls}
                    updateControls={updateControls}
                    mask={control as Controls.MaskControlState}
                    updateMask={updateControl}
                  />
                )}
                <S.AllClassToggle onClick={() => setAllClasses(true)}>
                  None
                </S.AllClassToggle>
                <S.AllClassToggle onClick={() => setAllClasses(false)}>
                  All
                </S.AllClassToggle>
              </S.ActionsWrapper>
            </S.Header>

            <ClassToggles
              type={type}
              filterString={classSearch}
              classStates={classStates}
              classSet={classSet}
              updateControl={updateControl}
            />
          </S.Wrapper>
        );
      })}
    </div>
  );
};
