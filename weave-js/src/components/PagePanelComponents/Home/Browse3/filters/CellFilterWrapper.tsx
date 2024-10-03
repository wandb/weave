/**
 * Wrap a cell with an Option+Click handler that adds a filter
 * with the corresponding field, operation, and value.
 */

import React from 'react';

export type OnAddFilter = (
  field: string,
  operator: string | null,
  value: any,
  rowId: string
) => void;
type CellFilterWrapperProps = {
  children: React.ReactNode;
  onAddFilter?: OnAddFilter;
  field: string;
  operation: string | null;
  value: any;
  rowId: string;
  style?: React.CSSProperties;
};

export const CellFilterWrapper = ({
  children,
  onAddFilter,
  field,
  operation,
  value,
  rowId,
  style,
}: CellFilterWrapperProps) => {
  const onClickCapture = onAddFilter
    ? (e: React.MouseEvent) => {
        // event.altKey - pressed Option key on Macs
        if (e.altKey) {
          e.stopPropagation();
          e.preventDefault();
          onAddFilter(field, operation, value, rowId);
        }
      }
    : undefined;

  return (
    <div style={style ?? {}} onClickCapture={onClickCapture}>
      {children}
    </div>
  );
};
