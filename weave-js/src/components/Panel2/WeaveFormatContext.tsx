import React from 'react';

export interface WeaveFormatContextType {
  numberAlign?: 'left' | 'right' | 'center' | 'justify' | 'initial' | 'inherit';
  numberJustifyContent?: string;
  stringSpacing?: boolean;
}

export const WeaveFormatContext = React.createContext<WeaveFormatContextType>({
  numberAlign: 'center',
  numberJustifyContent: 'space-around',
  stringSpacing: false,
});
