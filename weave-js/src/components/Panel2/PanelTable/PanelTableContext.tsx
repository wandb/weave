import React from 'react';

type PanelTableContextValue = {
  setHoveredColId: (value: string) => void;
  hoveredColId: string;
};

export const PanelTableContext = React.createContext<PanelTableContextValue>({
  setHoveredColId: () => {},
  hoveredColId: '',
});

export const usePanelTableContext = () => React.useContext(PanelTableContext);
export const PanelTableContextProvider = ({
  setHoveredColId,
  hoveredColId,
  ...props
}: PanelTableContextValue) => {
  return (
    <PanelTableContext.Provider
      value={{setHoveredColId, hoveredColId}}
      {...props}
    />
  );
};
