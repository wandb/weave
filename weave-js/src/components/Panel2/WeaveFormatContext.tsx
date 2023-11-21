import React from 'react';

export type WeaveFormatContextType = {
  numberTextAlign?: React.CSSProperties['textAlign'];
  numberJustifyContent?: string;
  numberAlignContent?: string;
  stringSpacing?: boolean;
};

export const WeaveFormatContext = React.createContext<WeaveFormatContextType>({
  numberTextAlign: 'center',
  numberJustifyContent: 'space-around',
  numberAlignContent: 'space-around',
  stringSpacing: false,
});
