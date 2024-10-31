import React, {FC, useCallback, useEffect,useState} from 'react';

const DEFAULT_PAGE_SIZE = 50;

export const TableNavigationContext = React.createContext<{
  setIDs?: (ids: string[]) => void;
  getNextID?: (currentID: string) => string | null;
  getPreviousID?: (currentID: string) => string | null;
  nextPageNeeded: boolean;
}>({
  setIDs: () => {},
  getNextID: () => null,
  getPreviousID: () => null,
  nextPageNeeded: false,
});

export const TableNavigationProvider: FC<{
  children: React.ReactNode;
  resetTrigger: any; // This can be any value that changes when you want to reset
}> = ({children, resetTrigger}) => {
  const [ids, setIDs] = useState<string[]>([]);
  const [nextPageNeeded, setNextPageNeeded] = useState(false);

  // Reset IDs when resetTrigger changes
  useEffect(() => {
    setIDs([]);
    setNextPageNeeded(false);
  }, [resetTrigger]);

  const getNextID = useCallback(
    (currentId: string) => {
      const nextIDIndex = ids.indexOf(currentId) + 1;
      if (nextIDIndex === ids.length && ids.length === DEFAULT_PAGE_SIZE) {
        setNextPageNeeded(true);
        return null;
      }
      if (nextIDIndex >= 0 && nextIDIndex < ids.length) {
        return ids[nextIDIndex];
      }
      if (nextPageNeeded) {
        setNextPageNeeded(false);
        return ids[0];
      }
      return null;
    },
    [ids, nextPageNeeded]
  );

  const getPreviousID = useCallback(
    (currentID: string) => {
      const prevIDIndex = ids.indexOf(currentID) - 1;
      if (prevIDIndex >= 0 && prevIDIndex < ids.length) {
        return ids[prevIDIndex];
      }
      return null;
    },
    [ids]
  );

  return (
    <TableNavigationContext.Provider
      value={{setIDs, getNextID, getPreviousID, nextPageNeeded}}>
      {children}
    </TableNavigationContext.Provider>
  );
};
