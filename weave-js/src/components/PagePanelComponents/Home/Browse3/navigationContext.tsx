import React, {FC, useCallback, useState} from 'react';

const DEFAULT_PAGE_SIZE = 50;

export const TableNavigationContext = React.createContext<{
  setIDs?: (ids: string[]) => void;
  getNextID?: (currentID: string) => string | null;
  getPrevID?: (currentID: string) => string | null;
  nextPageNeeded: boolean;
}>({
  setIDs: () => {},
  getNextID: () => null,
  getPrevID: () => null,
  nextPageNeeded: false,
});

export const TableNavigationProvider: FC<{children: React.ReactNode}> = ({
  children,
}) => {
  const [ids, setIDs] = useState<string[]>([]);
  const [nextPageNeeded, setNextPageNeeded] = useState(false);

  console.log('ids: ', ids);

  const getNextID = useCallback(
    (currentId: string) => {
      const nextIDIndex = ids.indexOf(currentId) + 1;
      if (nextIDIndex === ids.length && ids.length === DEFAULT_PAGE_SIZE) {
        // current ID was the last element in the list.
        // TODO: handle navigating to next page
        setNextPageNeeded(true);
        return null;
      }
      if (nextIDIndex >= 0 && nextIDIndex < ids.length) {
        return ids[nextIDIndex];
      }
      if (nextPageNeeded) {
        // TODO: implement
        setNextPageNeeded(false);
        return ids[0];
      }
      return null;
    },
    [ids, nextPageNeeded]
  );

  const getPrevID = useCallback(
    (currentID: string) => {
      const prevIDIndex = ids.indexOf(currentID) - 1;
      if (prevIDIndex >= 0 && prevIDIndex < ids.length) {
        return ids[prevIDIndex];
      }
      // TODO: handle navigating back to the previous page
      return null;
    },
    [ids]
  );

  return (
    <TableNavigationContext.Provider
      value={{setIDs, getNextID, getPrevID, nextPageNeeded}}>
      {children}
    </TableNavigationContext.Provider>
  );
};
