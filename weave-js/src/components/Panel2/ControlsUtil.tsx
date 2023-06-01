import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import Input from '@wandb/weave/common/components/Input';
import {BoundingBoxSliderControl} from '@wandb/weave/common/components/MediaCard';
import {gray500} from '@wandb/weave/common/css/globals.styles';
import {CompareOp} from '@wandb/weave/common/util/ops';
import React, {FC, MouseEventHandler} from 'react';
import {Checkbox, Dropdown} from 'semantic-ui-react';
import styled from 'styled-components';

import * as S from './ControlsUtil.styles';

interface BoxConfidenceControlProps extends BoundingBoxSliderControl {
  name: string;
  slideRange: {min: number; max: number};
  onDisableChange: () => void;
  onSliderChange: (v: number) => void;
  onOperatorChange: (v: CompareOp) => void;
}

export const BoxConfidenceControl: FC<BoxConfidenceControlProps> = ({
  name,
  disabled,
  onDisableChange,
  value,
  slideRange,
  onSliderChange,
  comparator,
  onOperatorChange,
}) => {
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
};

type SearchInputProps = {
  value: string;
  onChange: (newValue: string) => void;
};

export const SearchInput: FC<SearchInputProps> = ({value, onChange}) => {
  return (
    <S.InputWrapper>
      <Input
        icon={<LegacyWBIcon style={{cursor: 'pointer'}} name="search" />}
        iconPosition="left"
        value={value}
        placeholder="Search"
        onChange={(_, {value: searchString}) => onChange(searchString)}
      />
    </S.InputWrapper>
  );
};

export const VisibilityToggle: FC<{
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
  onClick?: MouseEventHandler<HTMLDivElement>;
}

export interface ClassToggleAllProps extends Omit<ClassToggleProps, 'color'> {
  name: 'all';
}

export type AnyClassToggle = ClassToggleProps | ClassToggleAllProps;

export const ClassToggle: FC<AnyClassToggle> = props => {
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
};
export interface LabelToggleProps {
  disabled: boolean;
  onClick?: MouseEventHandler<HTMLDivElement>;
}

export const LabelToggle: FC<LabelToggleProps> = props => {
  const {onClick, disabled, children} = props;
  return (
    <>
      <VisibilityToggle disabled={disabled} onClick={onClick} />
      {children}
    </>
  );
};

export const ControlTitle = styled.span`
  font-weight: 600;
`;

export type ClassToggleWithSliderProps = ClassToggleProps & {
  opacity: number;
  onOpacityChange: (o: number) => void;
};

export const ClassToggleWithSlider: FC<ClassToggleWithSliderProps> = props => {
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
};
