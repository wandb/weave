/**
 * This component is used within a FilterRow to allow toggling
 * status values on or off in the filter.
 */

import React from 'react';

import {Button} from '../../../../Button';
import {FILTER_TO_STATUS, StatusChip} from '../pages/common/StatusChip';

type ValueInputStatusProps = {
  value: string | undefined;
  onSetValue: (value: string) => void;
};

export const ValueInputStatus = ({
  value,
  onSetValue,
}: ValueInputStatusProps) => {
  const enabled = value ? value.split(',') : [];
  const onClick = (toToggle: string) => {
    if (value === toToggle) {
      // Can't remove the last selected status
      return;
    }
    if (enabled.includes(toToggle)) {
      onSetValue(enabled.filter(s => s !== toToggle).join(','));
    } else {
      const newValue = Object.keys(FILTER_TO_STATUS)
        .filter(s => enabled.includes(s) || toToggle === s)
        .join(',');
      onSetValue(newValue);
    }
  };
  return (
    <div>
      {Object.keys(FILTER_TO_STATUS).map(status => (
        <Button
          key={status}
          size="small"
          variant="ghost"
          active={enabled.includes(status)}
          onClick={() => onClick(status)}>
          <StatusChip value={FILTER_TO_STATUS[status]} iconOnly />
        </Button>
      ))}
    </div>
  );
};
