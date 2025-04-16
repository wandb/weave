import {Icon, IconName} from '@wandb/weave/components/Icon';
import _ from 'lodash';
import React from 'react';
import {Input} from 'semantic-ui-react';

import {Button} from '../../../components/Button';
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
  useStepperPlusMinus?: boolean; // This should be true for any new components that use the NumberInput component
  value?: number;
}

const NumberInput: React.FC<NumberInputProps> = ({
  useStepperPlusMinus = false,
  ...props
}) => {
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
      // If the value is empty, try falling back to the placeholder in case it's a number
      // since that's what the input will show. We will want to be able to shift the value
      // from the empty state in this case.
      const v = parseFloat(
        stringValue === '' ? props?.placeholder?.toString() ?? '' : stringValue
      );
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
    [onChange, ticks, stringValue, strideLength, min, max, props?.placeholder]
  );

  if (props.stepper && useStepperPlusMinus) {
    return (
      <div
        className="number-input-plus-minus flex items-center rounded px-4 outline outline-moon-200"
        style={props.containerStyle}>
        <Button
          icon="remove"
          onClick={() => shiftValue(-1)}
          variant="ghost"
          size="small"
        />
        <Input
          input={{
            ref: inputRef,
          }}
          aria-label={props.label}
          className={`number-input-plus-minus__input ${props.className || ''}`}
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
        <Button
          icon="add-new"
          onClick={() => shiftValue(1)}
          variant="ghost"
          size="small"
        />
      </div>
    );
  }

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
        style={{marginRight: 0, ...props.inputStyle}} // the default margin right is 4px but that misaligns the arrow buttons
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
