import React from 'react';

/**
 * Allow values to be specified by either props (a value and a setter callback) or
 * by internal state. When props are passed, their values are preferred over state.
 */
export default function useControllableState<T>(
  initialValueIfUncontrolled: T,
  controlledValue?: T,
  setControlledValue?: (value: T) => void
) {
  const [state, setState] = React.useState(initialValueIfUncontrolled);

  // NOTE: this hook can't be used where value might actually
  // be set to `undefined`

  if (
    (controlledValue !== undefined && setControlledValue === undefined) ||
    (controlledValue === undefined && setControlledValue !== undefined)
  ) {
    throw new Error(
      `Error: controlledValue is ${controlledValue} but setControlledValue is ${setControlledValue}. You must pass both or neither.`
    );
  }

  return [controlledValue ?? state, setControlledValue ?? setState] as const;
}
