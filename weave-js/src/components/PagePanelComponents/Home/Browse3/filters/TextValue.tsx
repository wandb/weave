import React from 'react';

import {TextField} from '../../../../Form/TextField';
import {FILTER_INPUT_DEBOUNCE_MS} from './FilterBar';

type TextValueProps = {
  value: string;
  onSetValue: (value: string) => void;
  type?: string;
  isActive?: boolean;
};

export const TextValue = ({
  value,
  onSetValue,
  type,
  isActive,
}: TextValueProps) => {
  const [localValue, setLocalValue] = React.useState(value);
  const debounceTimeoutRef = React.useRef<NodeJS.Timeout>();

  // Update local value when prop value changes
  React.useEffect(() => {
    setLocalValue(value);
  }, [value]);

  // Cleanup debounce timeout on unmount
  React.useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
    };
  }, []);

  const handleChange = (newValue: string) => {
    setLocalValue(newValue);

    // Clear existing timeout
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    // Set new timeout
    debounceTimeoutRef.current = setTimeout(() => {
      onSetValue(newValue);
    }, FILTER_INPUT_DEBOUNCE_MS);
  };

  return (
    <div className="ml-1 min-w-[200px]">
      <TextField
        type={type}
        value={localValue}
        onChange={handleChange}
        size="small"
        autoFocus={isActive}
      />
    </div>
  );
};
