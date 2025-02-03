import React, {FC, useCallback, useMemo, useState} from 'react';

export const TableRowSelectionContext = React.createContext<{
  rowIdsConfigured: boolean;
  rowIdInTable: (id: string) => boolean;
  setRowIds?: (rowIds: string[]) => void;
  getNextRowId?: (currentId: string) => string | null;
  getPreviousRowId?: (currentId: string) => string | null;
}>({
  rowIdsConfigured: false,
  rowIdInTable: (id: string) => false,
  setRowIds: () => {},
  getNextRowId: () => null,
  getPreviousRowId: () => null,
});

export const TableRowSelectionProvider: FC<{children: React.ReactNode}> = ({
  children,
}) => {
  const [rowIds, setRowIds] = useState<string[]>([]);
  const rowIdsConfigured = useMemo(() => rowIds.length > 0, [rowIds]);
  const rowIdInTable = useCallback(
    (currentId: string) => rowIds.includes(currentId),
    [rowIds]
  );

  const getNextRowId = useCallback(
    (currentId: string) => {
      const currentIndex = rowIds.indexOf(currentId);
      if (currentIndex !== -1) {
        return rowIds[currentIndex + 1];
      }
      return null;
    },
    [rowIds]
  );

  const getPreviousRowId = useCallback(
    (currentId: string) => {
      const currentIndex = rowIds.indexOf(currentId);
      if (currentIndex !== -1) {
        return rowIds[currentIndex - 1];
      }
      return null;
    },
    [rowIds]
  );

  return (
    <TableRowSelectionContext.Provider
      value={{
        rowIdsConfigured,
        rowIdInTable,
        setRowIds,
        getNextRowId,
        getPreviousRowId,
      }}>
      {children}
    </TableRowSelectionContext.Provider>
  );
};
