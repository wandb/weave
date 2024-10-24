import React, {FC, useCallback, useState} from 'react';

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

export const TableNavigationProvider: FC<{children: React.ReactNode}> = ({
  children,
}) => {
  const [ids, setIDs] = useState<string[]>([]);
  const [nextPageNeeded, setNextPageNeeded] = useState(false);

  const getNextID = useCallback(
    (currentId: string) => {
      const currentIndex = ids.indexOf(currentId);
      if (currentIndex === ids.length - 1 && ids.length === DEFAULT_PAGE_SIZE) {
        setNextPageNeeded(true);
      } else if (currentIndex !== -1) {
        return ids[currentIndex + 1];
      } else if (nextPageNeeded) {
        setNextPageNeeded(false);
        return ids[0];
      }
      return null;
    },
    [ids, nextPageNeeded]
  );

  const getPreviousID = useCallback(
    (currentID: string) => {
      const currentIndex = ids.indexOf(currentID);
      return ids[currentIndex - 1];
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
