import React from 'react';

export const PanelTableContext = React.createContext<{
  setHoveredColId: (value: string) => void;
  hoveredColId: string;
}>({setHoveredColId: () => {}, hoveredColId: ''});
export const usePanelTableContext = () => React.useContext(PanelTableContext);
export const PanelTableContextProvider = ({
  setHoveredColId,
  hoveredColId,
  children,
}) => {
  return (
    <PanelTableContext.Provider value={{setHoveredColId, hoveredColId}}>
      {children}
    </PanelTableContext.Provider>
  );
};
