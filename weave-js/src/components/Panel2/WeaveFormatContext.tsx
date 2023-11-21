import React from 'react';

export type WeaveFormatContextType = {
  numberAlign?: React.CSSProperties['textAlign'];
  numberJustifyContent?: string;
  stringSpacing?: boolean;
};

export const WeaveFormatContext = React.createContext<WeaveFormatContextType>({
  numberAlign: 'center',
  numberJustifyContent: 'space-around',
  stringSpacing: false,
});
