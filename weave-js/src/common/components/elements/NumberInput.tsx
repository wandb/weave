import _ from 'lodash';
import React from 'react';
import {Icon, Input} from 'semantic-ui-react';

import clamp from '../../util/clamp';

interface NumberInputProps {
  className?: string;
  value?: number;
  placeholder?: string;
  disabled?: boolean;
  stepper?: boolean;
  ticks?: number[];
  min?: number;
  max?: number;
  containerStyle?: React.CSSProperties;
  inputStyle?: React.CSSProperties;
  strideLength?: number;
  onChange: (newVal?: number) => void;
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

  // Shifts value up or down based on strideLength and available ticks
  const shiftValue = React.useCallback(
    (e: React.SyntheticEvent<HTMLInputElement>, direction: number) => {
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

      const t = e.currentTarget;
      t.value = newValue.toString();
      setStringValue(newValue.toString());
      onChange(newValue);
    },
    [onChange, ticks, stringValue, strideLength, min, max]
  );

  return (
    <div className="number-input__container" style={props.containerStyle}>
      <Input
        style={props.inputStyle}
        className={`number-input__input ${props.className || ''}`}
        type="number"
        disabled={props.disabled}
        placeholder={props.placeholder}
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
            shiftValue(e, direction);
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
        <div className="number-input__stepper">
          <Icon
            onClick={(e: React.SyntheticEvent<HTMLInputElement>) =>
              shiftValue(e, 1)
            }
            size="mini"
            name="chevron up"
          />
          <Icon
            onClick={(e: React.SyntheticEvent<HTMLInputElement>) =>
              shiftValue(e, -1)
            }
            size="mini"
            name="chevron down"
          />
        </div>
      )}
    </div>
  );
};

export default NumberInput;
