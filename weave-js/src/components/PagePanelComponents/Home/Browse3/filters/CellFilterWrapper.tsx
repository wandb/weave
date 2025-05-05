/**
 * Wrap a cell with an Option+Click handler that adds a filter
 * with the corresponding field, operation, and value.
 */

import React from 'react';

export type OnUpdateFilter = (
  field: string,
  operator: string | null,
  value: any,
  rowId: string
) => void;
type CellFilterWrapperProps = {
  children: React.ReactNode;
  onUpdateFilter?: OnUpdateFilter;
  field: string;
  operation: string | null;
  value: any;
  rowId: string;
  style?: React.CSSProperties;
};

export const CellFilterWrapper = ({
  children,
  onUpdateFilter,
  field,
  operation,
  value,
  rowId,
  style,
}: CellFilterWrapperProps) => {
  const onClickCapture = onUpdateFilter
    ? (e: React.MouseEvent) => {
        // event.altKey - pressed Option key on Macs
        if (e.altKey) {
          console.log('altKey', field, operation, value, rowId);
          e.stopPropagation();
          e.preventDefault();
          onUpdateFilter(field, operation, value, rowId);
        }
      }
    : undefined;

  return (
    <div style={style ?? {}} onClickCapture={onClickCapture}>
      {children}
    </div>
  );
};
