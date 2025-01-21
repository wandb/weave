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
        newVal = getClosestTick(newVal, sliderValue, min, max, ticks);
        setSliderValue(newVal);
        onChangeDebounced(newVal);
      },
      [ticks, min, max, sliderValue, onChangeDebounced]
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
          max={max}
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

export function getClosestTick(
  val: number,
  prev: number,
  min: number,
  max: number,
  ticks?: number[]
): number {
  // if min/max not in ticks, allow coercion to nearest value
  if (val > max) {
    return max;
  }
  if (val < min) {
    return min;
  }
  if (ticks === null || ticks === undefined) {
    return val;
  }

  let closest = val;
  const increasing = val > prev;
  let minDiff = Number.MAX_VALUE;

  // Binary search for the closest tick
  let left = 0;
  let right = ticks.length - 1;

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const tick = ticks[mid];
    const diff = Math.abs(tick - val);

    // Only update closest if the tick is in the right direction
    if (
      diff < minDiff &&
      ((increasing && tick >= val) || (!increasing && tick <= val))
    ) {
      closest = tick;
      if (closest === val) {
        break;
      }
      minDiff = diff;
    }

    if (tick < val) {
      left = mid + 1;
    } else {
      right = mid - 1;
    }
  }

  return closest;
}
