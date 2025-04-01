import {Icon, IconName} from '@wandb/weave/components/Icon';
import _ from 'lodash';
import React from 'react';
import {Input} from 'semantic-ui-react';

import clamp from '../../util/clamp';

interface NumberInputProps {
  className?: string;
  containerStyle?: React.CSSProperties;
  disabled?: boolean;
  inputStyle?: React.CSSProperties;
  label?: string;
  max?: number;
  min?: number;
  onChange: (newVal?: number) => void;
  placeholder?: string;
  stepper?: boolean;
  strideLength?: number;
  ticks?: number[];
  value?: number;
}

const NumberInput: React.FC<NumberInputProps> = props => {
  const [stringValue, setStringValue] = React.useState(
    props.value == null ? '' : props.value.toString()
  );

  const focusedRef = React.useRef(false);

  const setStateValueToProp = () => {
    setStringValue(props.value == null ? '' : props.value.toString());
  };

  React.useEffect(() => {
    if (!focusedRef.current) {
      setStateValueToProp();
    }
  });

  const {onChange, ticks, strideLength, min, max} = props;
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Shifts value up or down based on strideLength and available ticks
  const shiftValue = React.useCallback(
    (direction: number) => {
      if (direction == null) {
        // Do nothing on non arrow keys
        return;
      }
      const v = parseFloat(stringValue);
      let newValue;
      if (ticks) {
        if (strideLength) {
          const shift = direction * strideLength;
          newValue = clamp(shift + v, {
            min: ticks[0],
            max: ticks[ticks.length - 1],
          });
        } else {
          // When no stride length is set get the next valid step
          const currentIndex = _.sortedIndex(ticks, v);
          const finalIndex = clamp(currentIndex + direction, {
            min: 0,
            max: ticks.length - 1,
          });
          newValue = ticks[finalIndex];
        }
      } else {
        newValue = v + direction * (strideLength ?? 1);
        newValue = clamp(newValue, {min, max});
      }

      if (inputRef.current) {
        inputRef.current.value = newValue.toString();
      }
      setStringValue(newValue.toString());
      onChange(newValue);
    },
    [onChange, ticks, stringValue, strideLength, min, max]
  );

  return (
    <div className="number-input__container" style={props.containerStyle}>
      <Input
        input={{
          ref: inputRef,
        }}
        aria-label={props.label}
        className={`number-input__input ${props.className || ''}`}
        disabled={props.disabled}
        placeholder={props.placeholder}
        style={props.inputStyle}
        type="number"
        value={stringValue}
        onFocus={() => {
          focusedRef.current = true;
        }}
        onBlur={() => {
          focusedRef.current = false;
          setStateValueToProp();
        }}
        onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
          const direction =
            e.key === 'ArrowUp' ? 1 : e.key === 'ArrowDown' ? -1 : null;

          if (direction != null) {
            shiftValue(direction);
            e.preventDefault();
          }
        }}
        onChange={e => {
          const newVal = e.target.value;
          setStringValue(newVal);

          if (newVal === '') {
            props.onChange(undefined);
          } else {
            const newValFloat = parseFloat(newVal);
            if (!Number.isNaN(newValFloat) && newValFloat !== props.value) {
              const newValue = clamp(newValFloat, {
                min: props.min,
                max: props.max,
              });
              props.onChange(newValue);
            }
          }
        }}
      />
      {props.stepper && (
        <div className="number-input__stepper flex flex-col justify-center p-2 pr-4">
          <NumberInputArrow
            onChange={() => shiftValue(1)}
            iconName="chevron-up"
          />
          <NumberInputArrow
            onChange={() => shiftValue(-1)}
            iconName="chevron-down"
          />
        </div>
      )}
    </div>
  );
};

const NumberInputArrow = ({
  onChange,
  iconName,
}: {
  onChange: () => void;
  iconName: IconName;
}) => {
  return (
    <div
      className="flex h-full cursor-pointer flex-col items-center justify-center rounded-sm text-moon-600 hover:bg-moon-150"
      data-test={`number-input-arrow-${iconName}`}
      onClick={onChange}>
      <Icon width={10} height={10} name={iconName} />
    </div>
  );
};

export default NumberInput;
