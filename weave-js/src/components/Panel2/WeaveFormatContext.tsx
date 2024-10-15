import React from 'react';

type PanelNumberFormat = {
  textAlign?: React.CSSProperties['textAlign'];
  padding?: React.CSSProperties['padding'];
  justifyContent?: React.CSSProperties['justifyContent'];
  alignContent?: React.CSSProperties['alignContent'];
};

type PanelStringFormat = {
  spacing?: boolean;
};

type PanelColumnFormat = {
  textAlign?: React.CSSProperties['textAlign'];
};

export type WeaveFormatContextType = {
  numberFormat: PanelNumberFormat;
  stringFormat: PanelStringFormat;
  columnFormat: PanelColumnFormat;
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
  columnFormat: {
    textAlign: 'center',
  },
});
