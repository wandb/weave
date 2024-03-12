import LinkIcon from '@mui/icons-material/Link';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  TextField,
  Typography,
} from '@mui/material';
import {GridColDef, useGridApiRef} from '@mui/x-data-grid-pro';
import {useWeaveContext} from '@wandb/weave/context';
import {
  isAssignableTo,
  isTypedDict,
  listObjectType,
  maybe,
  ObjectType,
  OutputNode,
  Type,
  typedDictPropertyTypes,
  TypedDictType,
} from '@wandb/weave/core';
import {
  objectRefWithExtra,
  parseRef,
  refUri,
  WandbArtifactRef,
} from '@wandb/weave/react';
import * as _ from 'lodash';
import React, {
  createContext,
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {
  useWeaveflowCurrentRouteContext,
  WeaveflowPeekContext,
} from '../Browse3/context';
import {ValueViewPrimitive} from '../Browse3/pages/CallPage/ValueViewPrimitive';
import {Link} from '../Browse3/pages/common/Links';
import {
  DICT_KEY_EDGE_TYPE,
  LIST_INDEX_EDGE_TYPE,
  OBJECT_ATTRIBUTE_EDGE_TYPE,
} from '../Browse3/pages/wfReactInterface/constants';
import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';
import {TableQuery} from '../Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {StyledDataGrid} from '../Browse3/StyledDataGrid';
import {flattenObject, unflattenObject} from './browse2Util';
import {CellValue} from './CellValue';
import {
  mutationPublishArtifact,
  mutationSet,
  nodeToEasyNode,
  weaveGet,
} from './easyWeave';
import {parseRefMaybe, SmallRef} from './SmallRef';
import {useRefPageUrl} from './url';

const displaysAsSingleRow = (valueType: Type) => {
  if (valueType === 'none') {
    return true;
  }
  if (isAssignableTo(valueType, maybe({type: 'list', objectType: 'any'}))) {
    return false;
  }
  if (
    isAssignableTo(valueType, maybe({type: 'typedDict', propertyTypes: {}}))
  ) {
    return false;
  }
  return true;
  // const singleRowTypes: Type[] = ['string', 'boolean', 'number'];
  // return isAssignableTo(valueType, union(singleRowTypes.map(t => maybe(t))));
};

interface WeaveEditorPathElObject {
  type: 'getattr';
  key: string;
}

interface WeaveEditorPathElTypedDict {
  type: 'pick';
  key: string;
}

type WeaveEditorPathEl = WeaveEditorPathElObject | WeaveEditorPathElTypedDict;

interface WeaveEditorEdit {
  path: WeaveEditorPathEl[];
  newValue: any;
}

interface WeaveEditorContextValue {
  edits: WeaveEditorEdit[];
  addEdit: (edit: WeaveEditorEdit) => void;
}

const weaveEditorPathUrlPathPart = (path: WeaveEditorPathEl[]) => {
  // Return the url path for a given editor path
  return path.flatMap(pathEl => {
    if (pathEl.type === 'getattr') {
      return [OBJECT_ATTRIBUTE_EDGE_TYPE, pathEl.key];
    } else if (pathEl.type === 'pick') {
      return [DICT_KEY_EDGE_TYPE, pathEl.key];
    } else {
      throw new Error('invalid pathEl type');
    }
  });
};

const WeaveEditorContext = React.createContext<WeaveEditorContextValue>({
  edits: [],
  addEdit: () => {},
});

const useWeaveEditorContext = () => {
  return React.useContext(WeaveEditorContext);
};

const useWeaveEditorContextAddEdit = () => {
  return useWeaveEditorContext().addEdit;
};

const WeaveEditorCommit: FC<{
  objName: string;
  rootObjectRef: WandbArtifactRef;
  refWithType: RefWithType;
  edits: WeaveEditorEdit[];
  handleClose: () => void;
  handleClearEdits: () => void;
}> = ({
  objName,
  refWithType,
  rootObjectRef,
  edits,
  handleClose,
  handleClearEdits,
}) => {
  const {useApplyMutationsToRef} = useWFHooks();
  const refPageUrl = useRefPageUrl();
  const history = useHistory();
  const [working, setWorking] = useState<
    'idle' | 'addingRow' | 'publishing' | 'done'
  >('idle');
  const applyMutationsToRef = useApplyMutationsToRef();

  const handleSubmit = useCallback(async () => {
    setWorking('addingRow');
    const finalRootUri = await applyMutationsToRef(refWithType.refUri, edits);
    setWorking('done');
    handleClearEdits();
    history.push(refPageUrl(objName, finalRootUri));
    handleClose();
  }, [
    applyMutationsToRef,
    refWithType.refUri,
    edits,
    handleClearEdits,
    history,
    refPageUrl,
    objName,
    handleClose,
  ]);
  return (
    <Dialog fullWidth maxWidth="sm" open={true} onClose={handleClose}>
      <DialogTitle>Commit changes</DialogTitle>
      {working === 'idle' ? (
        <>
          <DialogContent>
            <Typography>Commit {edits.length} edits?</Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose}>Cancel</Button>
            <Button onClick={handleSubmit}>Commit</Button>
          </DialogActions>
        </>
      ) : (
        <>
          <DialogContent>
            <Typography>Mutating...</Typography>
            {(working === 'publishing' || working === 'done') && (
              <Typography>Publishing new version...</Typography>
            )}
            {working === 'done' && <Typography>Done</Typography>}
            {/* {working === 'done' && (
              <Box mt={2}>
                <Typography>
                  <Link to={refPageUrl('Dataset', newUri!)}>
                    View new version
                  </Link>
                </Typography>
              </Box>
            )} */}
          </DialogContent>
          <DialogActions>
            <Button disabled={working !== 'done'} onClick={handleClose}>
              Close
            </Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
};

export const WeaveEditorSourceContext = createContext<{
  entityName: string;
  projectName: string;
  objectName: string;
  objectVersionHash: string;
  filePath: string;
  refExtra?: string[];
} | null>(null);

const useObjectVersionLinkPathForPath = () => {
  const router = useWeaveflowCurrentRouteContext();
  const weaveEditorSourceContext = useContext(WeaveEditorSourceContext);
  if (weaveEditorSourceContext == null) {
    throw new Error('invalid weaveEditorSourceContext');
  }
  return useCallback(
    (path: string[]) => {
      return router.objectVersionUIUrl(
        weaveEditorSourceContext.entityName,
        weaveEditorSourceContext.projectName,
        weaveEditorSourceContext.objectName,
        weaveEditorSourceContext.objectVersionHash,
        weaveEditorSourceContext.filePath,
        (weaveEditorSourceContext.refExtra ?? []).concat(path).join('/')
      );
    },
    [
      router,
      weaveEditorSourceContext.entityName,
      weaveEditorSourceContext.filePath,
      weaveEditorSourceContext.objectName,
      weaveEditorSourceContext.objectVersionHash,
      weaveEditorSourceContext.projectName,
      weaveEditorSourceContext.refExtra,
    ]
  );
};

type RefWithType = {
  refUri: string;
  type: Type;
};

export const WeaveEditor: FC<{
  objType: string;
  objectRefUri: string;
  disableEdits?: boolean;
}> = ({objType, objectRefUri, disableEdits}) => {
  const {
    derived: {useRefsType},
  } = useWFHooks();
  // const weave = useWeaveContext();
  // const {stack} = usePanelContext();
  // const [refinedNode, setRefinedNode] = useState<NodeOrVoidNode>(voidNode());
  const [refType, setRefType] = useState<Type>();
  const rootObjectRef = useMemo(() => {
    const ref = parseRef(objectRefUri);
    ref.artifactRefExtra = undefined;
    return ref as WandbArtifactRef;
  }, [objectRefUri]);
  const [edits, setEdits] = useState<WeaveEditorEdit[]>([]);
  const addEdit = useCallback(
    (edit: WeaveEditorEdit) => {
      setEdits([...edits, edit]);
    },
    [edits]
  );
  const contextVal = useMemo(() => ({edits, addEdit}), [edits, addEdit]);
  const [commitChangesOpen, setCommitChangesOpen] = useState(false);
  const refsType = useRefsType([objectRefUri]);
  useEffect(() => {
    if (refsType.loading) {
      return;
    }
    if (refsType.result == null || refsType.result.length === 0) {
      return;
    }
    setRefType(refsType.result[0]);
    // const doRefine = async () => {
    //   const refined = await weave.refineNode(node, stack); // TODO (Tim): Audit and potentially remove this opGet
    //   // console.log('GOT REFINED', refined);
    //   setRefinedNode(refined);
    // };
    // doRefine();
  }, [refsType.loading, refsType.result]);
  const refWithType: RefWithType | undefined = useMemo(() => {
    if (refType == null) {
      return;
    }
    return {
      refUri: objectRefUri,
      type: refType!,
    };
  }, [objectRefUri, refType]);

  return refWithType == null ? (
    <div>loading</div>
  ) : (
    <WeaveEditorContext.Provider value={contextVal}>
      <Box mb={4}>
        <WeaveEditorField refWithType={refWithType} path={[]} disableEdits />
      </Box>
      {!disableEdits && (
        <>
          <Typography>{edits.length} Edits</Typography>
          <Button variant="outlined" onClick={() => setCommitChangesOpen(true)}>
            Commit
          </Button>
          {commitChangesOpen && (
            <WeaveEditorCommit
              objName={objType}
              rootObjectRef={rootObjectRef}
              refWithType={refWithType}
              edits={edits}
              handleClose={() => setCommitChangesOpen(false)}
              handleClearEdits={() => setEdits([])}
            />
          )}
        </>
      )}
    </WeaveEditorContext.Provider>
  );
};

const WeaveEditorField: FC<{
  refWithType: RefWithType;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({refWithType, path, disableEdits}) => {
  const weave = useWeaveContext();
  if (refWithType.type === 'none') {
    return <ValueViewPrimitive>null</ValueViewPrimitive>;
  }
  if (isAssignableTo(refWithType.type, maybe('boolean'))) {
    return (
      <WeaveEditorBoolean
        refWithType={refWithType}
        path={path}
        disableEdits={disableEdits}
      />
    );
  }
  if (isAssignableTo(refWithType.type, maybe('string'))) {
    return (
      <WeaveEditorString
        refWithType={refWithType}
        path={path}
        disableEdits={disableEdits}
      />
    );
  }
  if (isAssignableTo(refWithType.type, maybe('number'))) {
    return (
      <WeaveEditorNumber
        refWithType={refWithType}
        path={path}
        disableEdits={disableEdits}
      />
    );
  }
  if (
    isAssignableTo(
      refWithType.type,
      maybe({type: 'typedDict', propertyTypes: {}})
    )
  ) {
    return (
      <WeaveEditorTypedDict
        refWithType={refWithType}
        path={path}
        disableEdits={disableEdits}
      />
    );
  }
  if (
    isAssignableTo(
      refWithType.type,
      maybe({type: 'list', objectType: {type: 'typedDict', propertyTypes: {}}})
    )
  ) {
    return (
      <WeaveEditorTable
        refWithType={refWithType}
        path={path}
        disableEdits={disableEdits}
      />
    );
  }
  if (isAssignableTo(refWithType.type, maybe({type: 'Object'}))) {
    return (
      <WeaveEditorObject
        refWithType={refWithType}
        path={path}
        disableEdits={disableEdits}
      />
    );
  }
  if (isAssignableTo(refWithType.type, maybe({type: 'OpDef'}))) {
    return <WeaveViewSmallRef refWithType={refWithType} />;
  }
  if (isAssignableTo(refWithType.type, maybe({type: 'WandbArtifactRef'}))) {
    return <WeaveViewSmallRef refWithType={refWithType} />;
  }
  return <div>[No editor for type {weave.typeToString(refWithType.type)}]</div>;
};

const useValueOfRefUri = (refUri: string, tableQuery?: TableQuery) => {
  const {useRefsData} = useWFHooks();
  const data = useRefsData([refUri], tableQuery);
  return useMemo(() => {
    if (data.loading) {
      return {
        loading: true,
        result: undefined,
      };
    }
    if (data.result == null || data.result.length === 0) {
      return {
        loading: true,
        result: undefined,
      };
    }
    return {
      loading: false,
      result: data.result[0],
    };
  }, [data.loading, data.result]);
};

export const WeaveEditorBoolean: FC<{
  refWithType: RefWithType;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({refWithType, path, disableEdits}) => {
  const addEdit = useWeaveEditorContextAddEdit();
  const query = useValueOfRefUri(refWithType.refUri);

  const [curVal, setCurVal] = useState<boolean>(false);
  const loadedOnce = useRef(false);
  useEffect(() => {
    if (loadedOnce.current) {
      return;
    }
    if (query.loading) {
      return;
    }
    loadedOnce.current = true;
    setCurVal(query.result);
  }, [curVal, query.loading, query.result]);
  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      console.log('CHECKED', e.target.checked);
      setCurVal(e.target.checked);
      addEdit({path, newValue: !!e.target.checked});
    },
    [addEdit, path]
  );
  return (
    <Checkbox
      checked={curVal ?? false}
      onChange={onChange}
      disabled={disableEdits}
    />
  );
};

export const WeaveEditorString: FC<{
  refWithType: RefWithType;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({refWithType, path, disableEdits}) => {
  const addEdit = useWeaveEditorContextAddEdit();
  const query = useValueOfRefUri(refWithType.refUri);
  const [curVal, setCurVal] = useState<string>('');
  const loadedOnce = useRef(false);
  useEffect(() => {
    if (loadedOnce.current) {
      return;
    }
    if (query.loading) {
      return;
    }
    loadedOnce.current = true;
    setCurVal(query.result);
  }, [curVal, query.loading, query.result]);
  const onChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setCurVal(e.target.value);
  }, []);
  const commit = useCallback(() => {
    addEdit({path, newValue: curVal});
  }, [addEdit, curVal, path]);
  if (disableEdits) {
    return (
      <pre
        style={{
          width: '100%',
          whiteSpace: 'pre-line',
          fontSize: '16px',
          margin: '0',
          fontFamily: 'Source Sans Pro',
        }}>
        {curVal ?? ''}
      </pre>
    );
  }
  return (
    <TextField
      value={curVal ?? ''}
      onChange={onChange}
      onBlur={commit}
      multiline
      fullWidth
    />
  );
};

export const WeaveEditorNumber: FC<{
  refWithType: RefWithType;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({refWithType, path, disableEdits}) => {
  const addEdit = useWeaveEditorContextAddEdit();
  const query = useValueOfRefUri(refWithType.refUri);
  const [curVal, setCurVal] = useState<string>('');
  const loadedOnce = useRef(false);
  useEffect(() => {
    if (loadedOnce.current) {
      return;
    }
    if (query.loading) {
      return;
    }
    loadedOnce.current = true;
    setCurVal(query.result);
  }, [curVal, query.loading, query.result]);
  const onChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setCurVal(e.target.value);
  }, []);
  const commit = useCallback(() => {
    addEdit({path, newValue: curVal});
  }, [addEdit, curVal, path]);
  if (disableEdits) {
    return <Typography>{curVal ?? ''}</Typography>;
  }
  return (
    <TextField
      value={curVal ?? ''}
      onChange={onChange}
      onBlur={commit}
      inputProps={{inputMode: 'numeric', pattern: '[.0-9]*'}}
    />
  );
};

export const WeaveEditorTypedDict: FC<{
  refWithType: RefWithType;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({refWithType, path, disableEdits}) => {
  // const val = useNodeValue(node);
  // return <Typography>{JSON.stringify(val)}</Typography>;
  const makeLinkPath = useObjectVersionLinkPathForPath();
  return (
    <Grid container spacing={2}>
      {Object.entries(typedDictPropertyTypes(refWithType.type))
        .filter(([key, value]) => key !== 'type' && !key.startsWith('_'))
        .flatMap(([key, valueType]) => {
          const singleRow = displaysAsSingleRow(valueType);
          return [
            <Grid
              item
              key={key + '-key'}
              xs={singleRow ? 2 : 12}
              sx={{
                overflow: 'hidden',
                whiteSpace: 'nowrap',
                textOverflow: 'ellipsis',
              }}>
              <Typography>
                <Link
                  to={makeLinkPath([
                    ...weaveEditorPathUrlPathPart(path),
                    DICT_KEY_EDGE_TYPE,
                    key,
                  ])}>
                  {key}
                </Link>
              </Typography>
            </Grid>,
            <Grid item key={key + '-value'} xs={singleRow ? 10 : 12}>
              <Box ml={singleRow ? 0 : 2}>
                <WeaveEditorField
                  refWithType={{
                    refUri: refUri(
                      objectRefWithExtra(
                        parseRef(refWithType.refUri),
                        OBJECT_ATTRIBUTE_EDGE_TYPE + '/' + key
                      )
                    ),
                    type: (refWithType.type as TypedDictType).propertyTypes[
                      key
                    ] as Type,
                  }}
                  path={[...path, {type: 'pick', key}]}
                  disableEdits={disableEdits}
                />
              </Box>
            </Grid>,
          ];
        })}
    </Grid>
  );
};

const Table = styled.div`
  display: grid;
  grid-template-columns: auto 1fr; /* Two columns */
  gap: 16px 8px;
`;
Table.displayName = 'S.Table';

const Row = styled.div`
  grid-column: span 2;
`;
Row.displayName = 'S.Row';

export const WeaveEditorObject: FC<{
  refWithType: RefWithType;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({refWithType, path, disableEdits}) => {
  const makeLinkPath = useObjectVersionLinkPathForPath();
  return (
    <Table>
      {Object.entries(refWithType.type)
        .filter(([key, value]) => key !== 'type' && !key.startsWith('_'))
        .flatMap(([key, valueType]) => {
          const singleRow = displaysAsSingleRow(valueType);
          const label = (
            <Typography>
              <Link
                to={makeLinkPath([
                  ...weaveEditorPathUrlPathPart(path),
                  OBJECT_ATTRIBUTE_EDGE_TYPE,
                  key,
                ])}>
                {key}
              </Link>
            </Typography>
          );
          const value = (
            <Box>
              <WeaveEditorField
                refWithType={{
                  refUri: refUri(
                    objectRefWithExtra(
                      parseRef(refWithType.refUri),
                      OBJECT_ATTRIBUTE_EDGE_TYPE + '/' + key
                    )
                  ),
                  type: (refWithType.type as ObjectType)[key] as Type,
                }}
                path={[...path, {type: 'getattr', key}]}
                disableEdits={disableEdits}
              />
            </Box>
          );
          if (singleRow) {
            return [
              <div key={key + '-key'}>{label}</div>,
              <div key={key + '-value'}>{value}</div>,
            ];
          }
          return [
            <Row key={key + '-key'}>{label}</Row>,
            <Row key={key + '-value'}>{value}</Row>,
          ];
        })}
    </Table>
  );
};

const typeToDataGridColumnSpec = (
  type: Type,
  isPeeking?: boolean,
  disableEdits?: boolean
): GridColDef[] => {
  //   const cols: GridColDef[] = [];
  //   const colGrouping: GridColumnGroup[] = [];
  if (isAssignableTo(type, {type: 'typedDict', propertyTypes: {}})) {
    const maxWidth = window.innerWidth * (isPeeking ? 0.5 : 0.75);
    const propertyTypes = typedDictPropertyTypes(type);
    return Object.entries(propertyTypes).flatMap(([key, valueType]) => {
      const valTypeCols = typeToDataGridColumnSpec(valueType);
      if (valTypeCols.length === 0) {
        let colType = 'string';
        let editable = false;
        if (isAssignableTo(valueType, maybe('boolean'))) {
          editable = true;
          colType = 'boolean';
        } else if (isAssignableTo(valueType, maybe('number'))) {
          editable = true;
          colType = 'number';
        } else if (isAssignableTo(valueType, maybe('string'))) {
          editable = true;
        } else if (
          isAssignableTo(valueType, maybe({type: 'list', objectType: 'any'}))
        ) {
          return [
            {
              maxWidth,
              type: 'string',
              editable: false,
              field: key,
              headerName: key,
              renderCell: params => {
                return (
                  <Typography>
                    {params.row[key] == null
                      ? '-'
                      : `[${params.row[key].length} item list]`}
                  </Typography>
                );
              },
            },
          ];
        }
        return [
          {
            maxWidth,
            type: colType,
            editable: editable && !disableEdits,
            field: key,
            headerName: key,
            renderCell: params => {
              return <CellValue value={params.row[key] ?? ''} />;
            },
          },
        ];
      }
      return valTypeCols.map(col => ({
        ...col,
        maxWidth,
        field: `${key}.${col.field}`,
        headerName: `${key}.${col.field}`,
      }));
    });
  }
  return [];
};

const MAX_ROWS = 1000;

export const WeaveEditorTable: FC<{
  refWithType: RefWithType;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({refWithType, path, disableEdits}) => {
  const apiRef = useGridApiRef();
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const addEdit = useWeaveEditorContextAddEdit();
  const makeLinkPath = useObjectVersionLinkPathForPath();
  const objectType = listObjectType(refWithType.type);
  if (!isTypedDict(objectType)) {
    throw new Error('invalid node for WeaveEditorList');
  }
  const fetchQuery = useValueOfRefUri(refWithType.refUri, {
    columns: Object.keys(objectType.propertyTypes),
    limit: MAX_ROWS + 1,
  });
  const [isTruncated, setIsTruncated] = useState(false);
  const [sourceRows, setSourceRows] = useState<any[] | undefined>();
  useEffect(() => {
    if (sourceRows != null) {
      return;
    }
    if (fetchQuery.loading) {
      return;
    }
    setIsTruncated((fetchQuery.result ?? []).length > MAX_ROWS);
    setSourceRows((fetchQuery.result ?? []).slice(0, MAX_ROWS));
  }, [sourceRows, fetchQuery]);

  const gridRows = useMemo(
    () =>
      (sourceRows ?? []).map((row: {[key: string]: any}, i: number) => ({
        _origIndex: i,
        id: i,
        ...flattenObject(row),
      })),
    [sourceRows]
  );

  // Autosize when rows change
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      apiRef.current.autosizeColumns({
        includeHeaders: true,
        includeOutliers: true,
      });
    }, 0);
    return () => {
      clearInterval(timeoutId);
    };
  }, [gridRows, apiRef]);

  const processRowUpdate = useCallback(
    (updatedRow: {[key: string]: any}, originalRow: {[key: string]: any}) => {
      const curSourceRows = sourceRows ?? [];
      const curSourceRow = curSourceRows[originalRow._origIndex];

      const newSourceRow = unflattenObject(updatedRow);
      delete newSourceRow._origIndex;
      if (curSourceRow?.id == null) {
        // Don't include id if we didn't have it originally.
        delete newSourceRow.id;
      }

      const newSourceRows = [
        ...curSourceRows.slice(0, originalRow._origIndex),
        newSourceRow,
        ...curSourceRows.slice(originalRow._origIndex + 1),
      ];
      setSourceRows(newSourceRows);
      addEdit({path, newValue: newSourceRows});
      return updatedRow;
    },
    [path, addEdit, sourceRows]
  );
  const columnSpec: GridColDef[] = useMemo(() => {
    return [
      {
        field: '_origIndex',
        headerName: '',
        width: 50,
        renderCell: params => (
          <Link
            to={makeLinkPath([
              ...weaveEditorPathUrlPathPart(path),
              LIST_INDEX_EDGE_TYPE,
              params.row._origIndex,
            ])}>
            <LinkIcon />
          </Link>
        ),
      },
      ...typeToDataGridColumnSpec(objectType, isPeeking, disableEdits),
    ];
  }, [disableEdits, makeLinkPath, objectType, path, isPeeking]);
  return (
    <>
      {isTruncated && (
        <Alert severity="warning">
          Showing {MAX_ROWS.toLocaleString()} rows only.
        </Alert>
      )}
      <Box
        sx={{
          height: 460,
          width: '100%',
        }}>
        <StyledDataGrid
          keepBorders
          apiRef={apiRef}
          density="compact"
          experimentalFeatures={{columnGrouping: true}}
          rows={gridRows}
          columns={columnSpec}
          initialState={{
            pagination: {
              paginationModel: {
                pageSize: 10,
              },
            },
          }}
          loading={fetchQuery.loading}
          disableRowSelectionOnClick
          processRowUpdate={processRowUpdate}
        />
      </Box>
    </>
  );
};

export const WeaveViewSmallRef: FC<{
  refWithType: RefWithType;
}> = ({refWithType}) => {
  const opDefQuery = useValueOfRefUri(refWithType.refUri);
  const opDefRef = useMemo(
    () => parseRefMaybe(opDefQuery.result ?? ''),
    [opDefQuery.result]
  );
  if (opDefQuery.loading) {
    return <div>loading</div>;
  } else if (opDefRef != null) {
    return <SmallRef objRef={opDefRef} />;
  } else {
    return <div>invalid ref: {opDefQuery.result}</div>;
  }
};
