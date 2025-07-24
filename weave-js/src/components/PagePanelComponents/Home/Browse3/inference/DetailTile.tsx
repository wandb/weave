/**
 * This is a small box for highlighting key propeties of a model.
 */
import React from 'react';

type DetailTileProps = {
  header: string;
  children?: React.ReactNode;
  footer?: string;
  tooltip?: string;
};

// Used to preserve spacing when no footer is provided.
const NON_BREAKING_SPACE = '\u00A0';

export const DetailTile = ({
  header,
  children,
  footer,
  tooltip,
}: DetailTileProps) => {
  return (
    <div
      className="flex h-[96px] flex-[1_0_auto] flex-col whitespace-nowrap rounded-lg border border-moon-250 p-8"
      title={tooltip}>
      <div className="text-center text-sm font-semibold text-moon-600">
        {header}
      </div>
      <div className="flex flex-grow items-center justify-center">
        {children}
      </div>
      <div className="text-center text-sm text-moon-500">
        {footer ?? NON_BREAKING_SPACE}
      </div>
    </div>
  );
};
