import React from 'react';

type PanelNumberFormat = {
  textAlign?: React.CSSProperties['textAlign'];
  padding?: React.CSSProperties['padding'];
  justifyContent?: string;
  alignContent?: string;
};

type PanelStringFormat = {
  spacing?: boolean;
};

export type WeaveFormatContextType = {
  numberFormat: PanelNumberFormat;
  stringFormat: PanelStringFormat;
};

export const WeaveFormatContext = React.createContext<WeaveFormatContextType>({
  numberFormat: {
    textAlign: 'center',
    justifyContent: 'space-around',
    alignContent: 'space-around',
    padding: '0',
  },
  stringFormat: {
    spacing: false,
  },
});
