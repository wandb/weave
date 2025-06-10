/**
 * This is a small box for highlighting key propeties of a model.
 */
import React from 'react';

type DetailTileProps = {
  header: string;
  children?: React.ReactNode;
  footer?: string;
};

// Used to preserve spacing when no footer is provided.
const NON_BREAKING_SPACE = '\u00A0';

export const DetailTile = ({header, footer, children}: DetailTileProps) => {
  return (
    <div className="flex h-[96px] w-[170px] flex-col rounded-lg border border-moon-250 p-8">
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
