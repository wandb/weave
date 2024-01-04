import React from 'react';

type RequestedActionType = {
  onClick: (event: React.MouseEvent) => void;
  label: string;
  Icon: React.ReactNode;
};
type PagePanelControlContextValue = {
  requestAction: (id: string, action: RequestedActionType) => void;
  requestedActions: Record<string, RequestedActionType>;
};

const PagePanelControlContext =
  React.createContext<PagePanelControlContextValue>({
    // no-op
    requestAction: () => {},
    requestedActions: {},
  });

const usePagePanelControlContext = () => {
  return React.useContext(PagePanelControlContext);
};

export const usePagePanelControlRequestAction = () => {
  return usePagePanelControlContext().requestAction;
};

export const usePagePanelControlRequestedActions = () => {
  return usePagePanelControlContext().requestedActions;
};

export const PagePanelControlContextProvider: React.FC = ({children}) => {
  const [requestedActions, setRequestedActions] = React.useState<
    Record<string, RequestedActionType>
  >({});
  const requestAction = React.useCallback(
    (id: string, action: RequestedActionType) => {
      setRequestedActions(prev => ({...prev, [id]: action}));
    },
    []
  );
  const value = React.useMemo(
    () => ({
      requestAction,
      requestedActions,
    }),
    [requestAction, requestedActions]
  );

  return (
    <PagePanelControlContext.Provider value={value}>
      {children}
    </PagePanelControlContext.Provider>
  );
};
