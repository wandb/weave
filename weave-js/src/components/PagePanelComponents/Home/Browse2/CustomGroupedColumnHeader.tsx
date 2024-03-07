/**
 * When we have grouped columns in the grid we want the headerName,
 * which defaults to the field name, to be the full dotted path so
 * that we see that in the column selection dialog, while in the
 * header itself we only want to show the last segment of the path
 * so as not to repeat what's shown in the grouping.
 */

import React from 'react';

type CustomGroupedColumnProps = {
  field: string;
};

export const CustomGroupedColumnHeader = ({
  field,
}: CustomGroupedColumnProps) => {
  const tail = field.split('.').slice(-1)[0];
  return <span>{tail}</span>;
};
