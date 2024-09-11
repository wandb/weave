/**
 * Wrap a cell with an Option+Click handler that adds a filter
 * with the corresponding field, operation, and value.
 */

import React from 'react';

type CellFilterWrapperProps = {
  children: React.ReactNode;
  onAddFilter?: (key: string, operation: string | null, value: any) => void;
  field: string;
  operation: string | null;
  value: any;
  style?: React.CSSProperties;
};

export const CellFilterWrapper = ({
  children,
  onAddFilter,
  field,
  operation,
  value,
  style,
}: CellFilterWrapperProps) => {
  const onClickCapture = onAddFilter
    ? (e: React.MouseEvent) => {
        // event.altKey - pressed Option key on Macs
        if (e.altKey) {
          e.stopPropagation();
          e.preventDefault();
          onAddFilter(field, operation, value);
        }
      }
    : undefined;

  return (
    <div style={style ?? {}} onClickCapture={onClickCapture}>
      {children}
    </div>
  );
};
