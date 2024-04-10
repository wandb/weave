import {
  DataGridProProps,
  GridApiPro,
  GridColDef,
  GridRowHeightParams,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {isRef} from '../common/util';
import {useWFHooks} from '../wfReactInterface/context';
import {
  USE_TABLE_FOR_ARRAYS,
  WeaveCHTableSourceRefContext,
} from './DataTableView';
import {ObjectViewerGroupingCell} from './ObjectViewerGroupingCell';
import {mapObject, ObjectPath, traverse, TraverseContext} from './traverse';
import {ValueView} from './ValueView';

type Data = Record<string, any>;

type ObjectViewerProps = {
  apiRef: React.MutableRefObject<GridApiPro>;
  data: Data;
  isExpanded: boolean;
};

// Traverse the data and find all ref URIs.
const getRefs = (data: Data): string[] => {
  const refs = new Set<string>();
  traverse(data, (context: TraverseContext) => {
    if (isRef(context.value)) {
      refs.add(context.value);
    }
  });
  return Array.from(refs);
};

type RefValues = Record<string, any>; // ref URI to value

const refIsExpandable = (ref: string): boolean => {
  const parsed = parseRef(ref);
  if (isWeaveObjectRef(parsed)) {
    return (
      parsed.weaveKind === 'object' ||
      (parsed.weaveKind === 'table' &&
        parsed.artifactRefExtra != null &&
        parsed.artifactRefExtra.length > 0)
    );
  }
  return false;
};

export const ObjectViewer = ({apiRef, data, isExpanded}: ObjectViewerProps) => {
  const {useRefsData} = useWFHooks();
  const [resolvedData, setResolvedData] = useState<Data>(data);
  const dataRefs = useMemo(() => getRefs(data).filter(refIsExpandable), [data]);
  const [expandedRefs, setExpandedRefs] = useState<{[ref: string]: string}>({});
  const addExpandedRef = useCallback((path: string, ref: string) => {
    setExpandedRefs(eRefs => ({...eRefs, [path]: ref}));
  }, []);
  const refs = useMemo(() => {
    return Array.from(new Set([...dataRefs, ...Object.values(expandedRefs)]));
  }, [dataRefs, expandedRefs]);
  const refsData = useRefsData(refs);

  useEffect(() => {
    const resolvedRefData = refsData.result;

    const refValues: RefValues = {};
    for (const [r, v] of _.zip(refs, resolvedRefData)) {
      if (!r || !v) {
        // Shouldn't be possible
        continue;
      }
      let val = r;
      if (v == null) {
        console.error('Error resolving ref', r);
      } else {
        val = v;
        if (typeof val === 'object' && val !== null) {
          val = {
            ...v,
            _ref: r,
          };
        }
      }
      refValues[r] = val;
    }
    let resolved = data;
    let dirty = true;
    const mapper = (context: TraverseContext) => {
      if (isRef(context.value) && refValues[context.value] != null) {
        dirty = true;
        const res = refValues[context.value];
        delete refValues[context.value];
        return res;
      }
      return _.clone(context.value);
    };
    while (dirty) {
      dirty = false;
      resolved = mapObject(resolved, mapper);
    }
    setResolvedData(resolved);
  }, [data, refs, refsData.result]);

  const rows = useMemo(() => {
    const contexts: (TraverseContext & {
      isExpandableRef?: boolean;
    })[] = [];
    traverse(resolvedData, context => {
      if (context.depth !== 0) {
        const contextTail = context.path.tail();
        const isNullDescription =
          typeof contextTail === 'string' &&
          contextTail === 'description' &&
          context.valueType === 'null';
        // For now we'll hide all keys that start with an underscore, is a name field, or is a null description.
        // Eventually we might offer a user toggle to display them.
        if (context.path.hasHiddenKey() || isNullDescription) {
          return 'skip';
        }
        if (
          isRef(context.value) &&
          expandedRefs[context.path.toString()] == null &&
          context.depth > 1 &&
          refIsExpandable(context.value)
        ) {
          // if (refIsExpandable(context.value)) {
          // These are possibly expandable refs.
          contexts.push({
            ...context,
            isExpandableRef: true,
          });
          // contexts.push({
          //   depth: context.depth + 1,
          //   isLeaf: true,
          //   isExpandableRef: true,
          //   path: context.path.plus(''),
          //   value: '',
          //   valueType: 'string',
          // });
          // }
        } else {
          contexts.push(context);
        }
      }
      if (USE_TABLE_FOR_ARRAYS && context.valueType === 'array') {
        return 'skip';
      }
      return true;
    });

    return contexts.map((c, id) => ({id: c.path.toString(), ...c}));
  }, [expandedRefs, resolvedData]);

  const columns: GridColDef[] = useMemo(() => {
    return [
      {
        field: 'value',
        headerName: 'Value',
        flex: 1,
        sortable: false,
        renderCell: ({row}) => {
          let baseRef: string | undefined;
          const path: ObjectPath = row.path;
          for (let i = path.length() - 1; i >= 0; i--) {
            const ancestorPath = path.ancestor(-i);
            const ancestorExpandedRef = expandedRefs[ancestorPath.toString()];
            if (ancestorExpandedRef) {
              baseRef = ancestorExpandedRef;
              break;
            }
          }
          const inner = <ValueView data={row} isExpanded={isExpanded} />;
          if (baseRef) {
            return (
              <WeaveCHTableSourceRefContext.Provider value={baseRef}>
                {inner}
              </WeaveCHTableSourceRefContext.Provider>
            );
          }
          return inner;
        },
      },
    ];
  }, [expandedRefs, isExpanded]);

  const [expandedIds, setExpandedIds] = useState<Array<string | number>>([]);

  const groupingColDef: DataGridProProps['groupingColDef'] = useMemo(
    () => ({
      headerName: 'Path',
      hideDescendantCount: true,
      renderCell: params => {
        const refToExpand = params.row.value;
        return (
          <ObjectViewerGroupingCell
            {...params}
            onClick={() => {
              setExpandedIds(eIds => {
                if (eIds.includes(params.row.id)) {
                  return eIds.filter(id => id !== params.row.id);
                }
                return [...eIds, params.row.id];
              });
              if (isRef(refToExpand)) {
                addExpandedRef(params.row.id, refToExpand);
              }
            }}
          />
        );
      },
    }),
    [addExpandedRef]
  );

  const deepRows = useDeepMemo(rows);

  const updateRowExpand = useCallback(() => {
    expandedIds.forEach(id => {
      if (apiRef.current.getRow(id)) {
        const children = apiRef.current.getRowGroupChildren({groupId: id});
        if (children.length === 0) {
          return;
        }
        apiRef.current.setRowChildrenExpansion(id, true);
      }
    });
    // apiRef.current.getAllRowIds().forEach(id => {
    //   if (expandedIds.includes(id)) {
    //     const children = apiRef.current.getRowGroupChildren({groupId: id});
    //     if (children.length === 0) {
    //       return;
    //     }
    //     apiRef.current.setRowChildrenExpansion(id, true);
    //   }
    //   console.log({id}, !expandedIds.includes(id), !isExpanded);
    //   if (!expandedIds.includes(id) && !isExpanded) {
    //     return;
    //   }
    //   const children = apiRef.current.getRowGroupChildren({groupId: id});
    //   if (children.length === 0) {
    //     return;
    //   }
    //   const row = apiRef.current.getRow(id);
    //   console.log({row});
    //   // apiRef.current.setRowChildrenExpansion(id, true);
    // });
  }, [apiRef, expandedIds]);

  useEffect(() => {
    return apiRef.current.subscribeEvent('rowsSet', () => {
      updateRowExpand();
    });
  }, [apiRef, expandedIds, updateRowExpand]);

  const inner = useMemo(() => {
    return (
      <StyledDataGrid
        apiRef={apiRef}
        treeData
        getTreeDataPath={row => row.path.toStringArray()}
        rows={deepRows}
        columns={columns}
        defaultGroupingExpansionDepth={isExpanded ? -1 : 0}
        columnHeaderHeight={38}
        getRowHeight={(params: GridRowHeightParams) => {
          const isNonRefString =
            params.model.valueType === 'string' && !isRef(params.model.value);
          const isArray = params.model.valueType === 'array';
          const isTableRef =
            isRef(params.model.value) &&
            (parseRefMaybe(params.model.value) as any).weaveKind === 'table';
          if (
            isNonRefString ||
            (isArray && USE_TABLE_FOR_ARRAYS) ||
            isTableRef
          ) {
            return 'auto';
          }
          return 38;
        }}
        hideFooter
        rowSelection={false}
        disableColumnMenu={true}
        groupingColDef={groupingColDef}
        sx={{
          borderRadius: '0px',
          '& .MuiDataGrid-row:hover': {
            backgroundColor: 'inherit',
          },
          '& > div > div > div > div > .MuiDataGrid-row > .MuiDataGrid-cell': {
            paddingRight: '0px',
            // Consider removing this - might screw up other things
            paddingLeft: '0px',
            // only the first cell
            '&:first-child': {
              paddingRight: '8px',
            },
          },
        }}
      />
    );
  }, [apiRef, columns, deepRows, groupingColDef, isExpanded]);
  return <div style={{overflow: 'hidden'}}>{inner}</div>;
};
