import React from 'react';

type DetailTileProps = {
  header: string;
  footer?: string;
};

export const DetailTile = ({header, footer}: DetailTileProps) => {
  return (
    <div className="flex h-[96px] w-[150px] flex-col border border-moon-250">
      <div className="text-center text-sm font-semibold">{header}</div>
      <div className="text-center text-sm text-moon-500">{footer}</div>
    </div>
  );
};
