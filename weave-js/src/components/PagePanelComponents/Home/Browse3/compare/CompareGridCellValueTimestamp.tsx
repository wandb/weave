/**
 * When we have an integer that appears to be a timestamp, we display it as a
 * nice date, but allow clicking to toggle between that and the raw value.
 */
import React, {useState} from 'react';

import {Timestamp} from '../../../../Timestamp';
import {Tooltip} from '../../../../Tooltip';

type CompareGridCellValueTimestampProps = {
  value: number;
  unit: 'ms' | 's';
};

export const CompareGridCellValueTimestamp = ({
  value,
  unit,
}: CompareGridCellValueTimestampProps) => {
  const [showRaw, setShowRaw] = useState(false);

  let body = null;
  if (showRaw) {
    body = (
      <Tooltip
        trigger={<span>{value}</span>}
        content="Click to format as date"
      />
    );
  } else {
    const tsValue = unit === 'ms' ? value / 1000 : value;
    body = <Timestamp value={tsValue} />;
  }

  return (
    <div className="cursor-pointer" onClick={() => setShowRaw(!showRaw)}>
      {body}
    </div>
  );
};
