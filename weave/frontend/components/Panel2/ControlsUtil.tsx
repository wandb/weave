import * as S from './ControlsUtil.styles';
import React from 'react';
import styled from 'styled-components';
import {gray500} from '@wandb/common/css/globals.styles';
import makeComp from '@wandb/common/util/profiler';
import LegacyWBIcon from '@wandb/common/components/elements/LegacyWBIcon';
import Input from '@wandb/common/components/Input';

import SliderInput from '@wandb/common/components/elements/SliderInput';
import {Checkbox, Dropdown} from 'semantic-ui-react';
import {CompareOp} from '@wandb/common/util/ops';
import {BoundingBoxSliderControl} from '@wandb/common/components/MediaCard';

interface BoxConfidenceControl extends BoundingBoxSliderControl {
  name: string;
  slideRange: {min: number; max: number};
  onDisableChange: () => void;
  onSliderChange: (v: number) => void;
  onOperatorChange: (v: CompareOp) => void;
}

export const BoxConfidenceControl = makeComp<BoxConfidenceControl>(
  props => {
    const {
      name,
      disabled,
      onDisableChange,
      value,
      slideRange,
      onSliderChange,
      comparator,
      onOperatorChange,
    } = props;

    const currentMin = parseFloat(slideRange.min.toPrecision(3));
    const currentMax = parseFloat(slideRange.max.toPrecision(3));

    return (
      <div className="confidence-slider__container">
        <Checkbox
          className="confidence-slider__toggle"
          checked={!disabled}
          onChange={onDisableChange}
        />
        <div className={'confidence-slider__key'}>{name}</div>
        <Dropdown
          className={'confidence-slider__op'}
          inline
          options={[
            {
              text: <span className="symbol">≥</span>,
              value: 'gte',
              key: 'gte',
            },
            {
              text: <span className="symbol">≤</span>,
              value: 'lte',
              key: 'lte',
            },
          ]}
          onChange={(_, {value: op}) => onOperatorChange(op as CompareOp)}
          value={comparator}
        />
        <SliderInput
          className={'confidence-slider__value'}
          sliderInPopup
          min={currentMin}
          max={currentMax}
          minLabel={currentMin.toString()}
          maxLabel={currentMax.toString()}
          step={(currentMax - currentMin) / 100}
          value={value}
          hasInput
          onChange={onSliderChange}
        />
      </div>
    );
  },
  {id: 'BoxConfidenceControl'}
);

export const SearchInput = makeComp<{
  value: string;
  onChange: (newValue: string) => void;
}>(
  ({value, onChange}) => {
    return (
      <S.InputWrapper>
        <Input
          icon={
            <LegacyWBIcon
              style={{cursor: 'pointer'}}
              name="search"></LegacyWBIcon>
          }
          iconPosition="left"
          value={value}
          placeholder="Search"
          onChange={(_, {value: searchString}) => onChange(searchString)}
        />
      </S.InputWrapper>
    );
  },
  {id: 'ControlSearchInput'}
);

export const VisibilityToggle: React.FC<{
  disabled?: boolean;
  onClick?: any;
}> = ({disabled, onClick}) => {
  return (
    <LegacyWBIcon
      style={{cursor: 'pointer'}}
      onClick={onClick}
      name={disabled ? 'hide' : 'show'}
    />
  );
};

export interface ClassToggleProps {
  name: string;
  disabled: boolean;
  color: string;
  onClick?: React.MouseEventHandler<HTMLDivElement>;
}

export interface ClassToggleAllProps extends Omit<ClassToggleProps, 'color'> {
  name: 'all';
}

export type AnyClassToggle = ClassToggleProps | ClassToggleAllProps;

export const ClassToggle = makeComp<AnyClassToggle>(
  props => {
    const {name, onClick, disabled} = props;
    return name === 'all' ? (
      <VisibilityToggle disabled={disabled} onClick={onClick} />
    ) : (
      <div
        onClick={onClick}
        className="mask-control__button"
        style={{
          userSelect: 'none',
          margin: 2,
          borderWidth: 0,
          background: disabled ? gray500 : (props as ClassToggleProps).color,
        }}>
        {name}
      </div>
    );
  },
  {id: 'ClassToggleButton'}
);
export interface LabelToggleProps {
  disabled: boolean;
  onClick?: React.MouseEventHandler<HTMLDivElement>;
}

export const LabelToggle = makeComp<LabelToggleProps>(
  props => {
    const {onClick, disabled, children} = props;
    return (
      <>
        <VisibilityToggle disabled={disabled} onClick={onClick} />
        {children}
      </>
    );
  },
  {id: 'LabelToggleButton'}
);

export const ControlTitle = styled.span`
  font-weight: 600;
`;

export type ClassToggleWithSlider = ClassToggleProps & {
  opacity: number;
  onOpacityChange: (o: number) => void;
};

export const ClassToggleWithSlider = makeComp<ClassToggleWithSlider>(
  props => {
    const {opacity, onOpacityChange, ...classToggleProps} = props;
    return (
      <SliderInput
        className={'panel-media__class-slider'}
        sliderInPopup
        value={opacity}
        min={0}
        minLabel={'0'}
        max={1}
        maxLabel={'1'}
        step={0.01}
        onChange={onOpacityChange}
        debounceTime={50}
        trigger={<ClassToggle {...classToggleProps} />}
      />
    );
  },
  {
    id: 'ClassToggleWithSlider',
  }
);
