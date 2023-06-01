import classNames from 'classnames';
import _ from 'lodash';
import React from 'react';
import {Popup} from 'semantic-ui-react';

import {ID} from '../../util/id';
// Doesn't yet work in nested panels yet.
// import {BetterPopup} from '../BetterPopup';
import NumberInput from './NumberInput';

export interface SliderInputProps {
  min: number;
  max: number;
  step: number;
  value?: number;
  // if true, only input will be displayed, with slider appearing in a hover popup
  sliderInPopup?: boolean;
  className?: string;
  debounceTime?: number;
  trigger?: JSX.Element;
  hasInput?: boolean;
  minLabel?: string;
  maxLabel?: string;
  ticks?: number[];
  disabled?: boolean;
  strideLength?: number;
  // if true, the slider will be restricted to props.max, but the input will be unbounded (https://wandb.atlassian.net/browse/WB-5666)
  allowGreaterThanMax?: boolean;
  onChange(value: number): void;
}

export const INPUT_SLIDER_CLASS = 'input__slider';

const SliderInput: React.FC<SliderInputProps> = React.memo(
  ({
    min,
    max,
    step,
    value,
    sliderInPopup,
    className,
    debounceTime,
    trigger,
    hasInput,
    minLabel,
    maxLabel,
    ticks,
    disabled,
    strideLength,
    allowGreaterThanMax,
    onChange,
  }) => {
    const [sliderValue, setSliderValue] = React.useState(value ?? 0);

    const tickListID = React.useMemo(() => ID(10), []);

    // eslint-disable-next-line react-hooks/exhaustive-deps
    const onChangeDebounced = React.useCallback(
      _.debounce((v: number) => {
        onChange(v);
      }, debounceTime || 1),
      [onChange, debounceTime]
    );
    // Cancel any potentially-still-running debounce method on cleanup
    React.useLayoutEffect(() => {
      return () => onChangeDebounced.flush();
    }, [onChangeDebounced]);

    const update = React.useCallback(
      (newVal: number | undefined) => {
        if (newVal == null || !_.isFinite(newVal)) {
          return;
        }
        if (newVal > max && !allowGreaterThanMax) {
          newVal = max;
        }
        if (newVal < min) {
          newVal = min;
        }
        if (ticks != null) {
          newVal = getClosestTick(ticks, newVal);
        }
        setSliderValue(newVal);
        onChangeDebounced(newVal);
      },
      [ticks, min, max, allowGreaterThanMax, onChangeDebounced]
    );

    React.useEffect(() => {
      if (value != null) {
        setSliderValue(value);
      }
    }, [value]);

    const tickDatalist = React.useMemo(
      () =>
        ticks && (
          <datalist id={tickListID}>
            {ticks.map((t, i) => (
              <option key={i} value={t}></option>
            ))}
          </datalist>
        ),
      [tickListID, ticks]
    );

    const renderSlider = () => {
      return (
        <div style={{display: 'flex', alignItems: 'center'}}>
          {minLabel && <label className="min">{minLabel}</label>}
          <input
            // Other code relies on this class to detect if the event
            // comes from a slider, do not remove.
            type="range"
            disabled={disabled ?? false}
            min={min}
            max={max}
            step={step}
            value={sliderValue}
            list={tickListID}
            onInput={(e: React.SyntheticEvent<HTMLInputElement>) => {
              const newVal = parseFloat(e.currentTarget.value);
              update(newVal);
            }}
            // suppress warning about onChange missing
            onChange={(e: React.SyntheticEvent<HTMLInputElement>) => {}}
          />
          {maxLabel && <label className="max">&nbsp;{maxLabel}</label>}
          {tickDatalist}
        </div>
      );
    };

    const renderInput = () => {
      return (
        <NumberInput
          stepper
          strideLength={strideLength}
          disabled={disabled ?? false}
          min={min}
          max={allowGreaterThanMax ? undefined : max}
          value={value}
          ticks={ticks}
          onChange={update}
        />
      );
    };

    return (
      <div className={classNames('slider-input', className)}>
        {sliderInPopup ? (
          <Popup
            inverted
            size="mini"
            className={INPUT_SLIDER_CLASS}
            hoverable
            position="top center"
            // on="click"
            trigger={<span>{trigger ?? renderInput()}</span>}
            content={<div className="slider-input">{renderSlider()}</div>}
          />
        ) : (
          <>
            {renderSlider()}
            {trigger ?? (hasInput && renderInput())}
          </>
        )}
      </div>
    );
  }
);

export default SliderInput;

function getClosestTick(ticks: number[], val: number): number {
  let closest = val;
  let minDiff = Number.MAX_VALUE;

  for (const tick of ticks) {
    const diff = Math.abs(tick - val);
    if (diff >= minDiff) {
      break;
    }
    closest = tick;
    minDiff = diff;
  }

  return closest;
}
