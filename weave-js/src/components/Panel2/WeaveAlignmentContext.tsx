import React from 'react';

export const WeaveAlignmentContext = React.createContext<{
  isInTable?: boolean;
  isInRow?: boolean;
}>({
  isInTable: false,
  isInRow: false, // PanelRow renders Lists of items
});
