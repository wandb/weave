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
import {
  DataGridPro as DataGrid,
  GridColDef,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {usePanelContext} from '@wandb/weave/components/Panel2/PanelContext';
import {useWeaveContext} from '@wandb/weave/context';
import {
  constFunction,
  constNumber,
  constString,
  isAssignableTo,
  isConstNode,
  isTypedDict,
  linearize,
  listObjectType,
  maybe,
  Node,
  NodeOrVoidNode,
  opDict,
  opLimit,
  opMap,
  opObjGetAttr,
  opPick,
  OutputNode,
  Type,
  typedDictPropertyTypes,
  voidNode,
} from '@wandb/weave/core';
import {
  isWandbArtifactRef,
  parseRef,
  useNodeValue,
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

import {useWeaveflowCurrentRouteContext} from '../Browse3/context';
import {Link} from '../Browse3/pages/common/Links';
import {flattenObject, unflattenObject} from './browse2Util';
import {
  mutationPublishArtifact,
  mutationSet,
  nodeToEasyNode,
  weaveGet,
} from './easyWeave';
import {parseRefMaybe, SmallRef} from './SmallRef';
import {useRefPageUrl} from './url';

const displaysAsSingleRow = (valueType: Type) => {
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
      return ['atr', pathEl.key];
    } else if (pathEl.type === 'pick') {
      return ['key', pathEl.key];
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
  objType: string;
  rootObjectRef: WandbArtifactRef;
  node: Node;
  edits: WeaveEditorEdit[];
  handleClose: () => void;
  handleClearEdits: () => void;
}> = ({objType, rootObjectRef, node, edits, handleClose, handleClearEdits}) => {
  const weave = useWeaveContext();
  const refPageUrl = useRefPageUrl();
  const history = useHistory();
  const [working, setWorking] = useState<
    'idle' | 'addingRow' | 'publishing' | 'done'
  >('idle');
  const handleSubmit = useCallback(async () => {
    setWorking('addingRow');

    let workingRootNode = node;

    for (const edit of edits) {
      let targetNode = nodeToEasyNode(workingRootNode as OutputNode);
      for (const pathEl of edit.path) {
        if (pathEl.type === 'getattr') {
          targetNode = targetNode.getAttr(pathEl.key);
        } else if (pathEl.type === 'pick') {
          targetNode = targetNode.pick(pathEl.key);
        } else {
          throw new Error('invalid pathEl type');
        }
      }
      const workingRootUri = await mutationSet(
        weave,
        targetNode,
        edit.newValue
      );
      workingRootNode = weaveGet(workingRootUri);
    }

    setWorking('publishing');

    // Returns final root uri if we need it.
    const finalRootUri = await mutationPublishArtifact(
      weave,
      // Local branch
      workingRootNode,
      // Target branch
      rootObjectRef.entityName,
      rootObjectRef.projectName,
      rootObjectRef.artifactName
    );

    // if ((orm?.projectConnection as WFNaiveProject).reload) {
    //   await (orm!.projectConnection as WFNaiveProject).reload();
    // }

    setWorking('done');

    handleClearEdits();
    history.push(refPageUrl(objType, finalRootUri));
    handleClose();
  }, [
    node,
    weave,
    rootObjectRef.entityName,
    rootObjectRef.projectName,
    rootObjectRef.artifactName,
    handleClearEdits,
    history,
    refPageUrl,
    objType,
    handleClose,
    edits,
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

export const WeaveEditor: FC<{
  objType: string;
  node: Node;
  disableEdits?: boolean;
}> = ({objType, node, disableEdits}) => {
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const [refinedNode, setRefinedNode] = useState<NodeOrVoidNode>(voidNode());
  const rootObjectRef = useMemo(() => {
    const linearNodes = linearize(node);
    if (linearNodes == null) {
      throw new Error('invalid node for WeaveEditor');
    }
    const node0 = linearNodes[0];
    if (!node0.fromOp.name.endsWith('get')) {
      throw new Error('invalid node for WeaveEditor');
    }
    if (node0.fromOp.inputs.uri == null) {
      throw new Error('invalid node for WeaveEditor');
    }
    if (!isConstNode(node0.fromOp.inputs.uri)) {
      throw new Error('invalid node for WeaveEditor');
    }
    const ref = parseRef(node0.fromOp.inputs.uri.val);
    if (!isWandbArtifactRef(ref)) {
      throw new Error('invalid node for WeaveEditor');
    }
    return ref;
  }, [node]);
  const [edits, setEdits] = useState<WeaveEditorEdit[]>([]);
  const addEdit = useCallback(
    (edit: WeaveEditorEdit) => {
      setEdits([...edits, edit]);
    },
    [edits]
  );
  const contextVal = useMemo(() => ({edits, addEdit}), [edits, addEdit]);
  const [commitChangesOpen, setCommitChangesOpen] = useState(false);
  useEffect(() => {
    const doRefine = async () => {
      const refined = await weave.refineNode(node, stack);
      // console.log('GOT REFINED', refined);
      setRefinedNode(refined);
    };
    doRefine();
  }, [node, stack, weave]);
  return refinedNode.nodeType === 'void' ? (
    <div>loading</div>
  ) : (
    <WeaveEditorContext.Provider value={contextVal}>
      <Box mb={4}>
        <WeaveEditorField node={refinedNode} path={[]} disableEdits />
      </Box>
      {!disableEdits && (
        <>
          <Typography>{edits.length} Edits</Typography>
          <Button variant="outlined" onClick={() => setCommitChangesOpen(true)}>
            Commit
          </Button>
          {commitChangesOpen && (
            <WeaveEditorCommit
              objType={objType}
              rootObjectRef={rootObjectRef}
              node={refinedNode}
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
  node: Node;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({node, path, disableEdits}) => {
  const weave = useWeaveContext();
  if (isAssignableTo(node.type, maybe('boolean'))) {
    return <WeaveEditorBoolean node={node} path={path} disableEdits />;
  }
  if (isAssignableTo(node.type, maybe('string'))) {
    return <WeaveEditorString node={node} path={path} disableEdits />;
  }
  if (isAssignableTo(node.type, maybe('number'))) {
    return <WeaveEditorNumber node={node} path={path} disableEdits />;
  }
  if (
    isAssignableTo(node.type, maybe({type: 'typedDict', propertyTypes: {}}))
  ) {
    return <WeaveEditorTypedDict node={node} path={path} disableEdits />;
  }
  if (
    isAssignableTo(
      node.type,
      maybe({type: 'list', objectType: {type: 'typedDict', propertyTypes: {}}})
    )
  ) {
    return <WeaveEditorTable node={node} path={path} disableEdits />;
  }
  if (isAssignableTo(node.type, maybe({type: 'Object'}))) {
    return <WeaveEditorObject node={node} path={path} disableEdits />;
  }
  if (isAssignableTo(node.type, maybe({type: 'OpDef'}))) {
    return <WeaveViewSmallRef node={node} />;
  }
  if (isAssignableTo(node.type, maybe({type: 'WandbArtifactRef'}))) {
    return <WeaveViewSmallRef node={node} />;
  }
  return <div>[No editor for type {weave.typeToString(node.type)}]</div>;
};

export const WeaveEditorBoolean: FC<{
  node: Node;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({node, path, disableEdits}) => {
  const addEdit = useWeaveEditorContextAddEdit();
  const query = useNodeValue(node);
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
  node: Node;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({node, path, disableEdits}) => {
  const addEdit = useWeaveEditorContextAddEdit();
  const query = useNodeValue(node);
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
  node: Node;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({node, path, disableEdits}) => {
  const addEdit = useWeaveEditorContextAddEdit();
  const query = useNodeValue(node);
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
  node: Node;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({node, path, disableEdits}) => {
  // const val = useNodeValue(node);
  // return <Typography>{JSON.stringify(val)}</Typography>;
  const makeLinkPath = useObjectVersionLinkPathForPath();
  return (
    <Grid container spacing={2}>
      {Object.entries(typedDictPropertyTypes(node.type))
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
                    'key',
                    key,
                  ])}>
                  {key}
                </Link>
              </Typography>
            </Grid>,
            <Grid item key={key + '-value'} xs={singleRow ? 10 : 12}>
              <Box ml={singleRow ? 0 : 2}>
                <WeaveEditorField
                  node={opPick({
                    obj: node,
                    key: constString(key.replace('.', '\\.')),
                  })}
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

export const WeaveEditorObject: FC<{
  node: Node;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({node, path, disableEdits}) => {
  const makeLinkPath = useObjectVersionLinkPathForPath();
  return (
    <Grid container spacing={2}>
      {Object.entries(node.type)
        .filter(([key, value]) => key !== 'type' && !key.startsWith('_'))
        .flatMap(([key, valueType]) => {
          const singleRow = displaysAsSingleRow(valueType);
          return [
            <Grid item key={key + '-key'} xs={singleRow ? 2 : 12}>
              <Typography>
                <Link
                  to={makeLinkPath([
                    ...weaveEditorPathUrlPathPart(path),
                    'atr',
                    key,
                  ])}>
                  {key}
                </Link>
              </Typography>
            </Grid>,
            <Grid item key={key + '-value'} xs={singleRow ? 10 : 12}>
              <Box ml={singleRow ? 0 : 2}>
                <WeaveEditorField
                  node={opObjGetAttr({self: node, name: constString(key)})}
                  path={[...path, {type: 'getattr', key}]}
                  disableEdits={disableEdits}
                />
              </Box>
            </Grid>,
          ];
        })}
    </Grid>
  );
};

const typeToDataGridColumnSpec = (
  type: Type,
  disableEdits?: boolean
): GridColDef[] => {
  //   const cols: GridColDef[] = [];
  //   const colGrouping: GridColumnGroup[] = [];
  if (isAssignableTo(type, {type: 'typedDict', propertyTypes: {}})) {
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
            type: colType,
            editable: editable && !disableEdits,
            field: key,
            headerName: key,
          },
        ];
      }
      return valTypeCols.map(col => ({
        ...col,
        field: `${key}.${col.field}`,
        headerName: `${key}.${col.field}`,
      }));
    });
  }
  return [];
};

const MAX_ROWS = 1000;

export const WeaveEditorTable: FC<{
  node: Node;
  path: WeaveEditorPathEl[];
  disableEdits?: boolean;
}> = ({node, path, disableEdits}) => {
  const apiRef = useGridApiRef();
  const addEdit = useWeaveEditorContextAddEdit();
  const makeLinkPath = useObjectVersionLinkPathForPath();
  const objectType = listObjectType(node.type);
  if (!isTypedDict(objectType)) {
    throw new Error('invalid node for WeaveEditorList');
  }
  const fetchAllNode = useMemo(() => {
    return opLimit({
      arr: opMap({
        arr: node,
        mapFn: constFunction({row: objectType}, ({row}) =>
          opDict(
            _.fromPairs(
              Object.keys(objectType.propertyTypes).map(key => [
                key,
                opPick({obj: row, key: constString(key)}),
              ])
            ) as any
          )
        ),
      }),
      limit: constNumber(MAX_ROWS + 1),
    });
  }, [node, objectType]);
  const fetchQuery = useNodeValue(fetchAllNode);

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
              'ndx',
              params.row._origIndex,
            ])}>
            <LinkIcon />
          </Link>
        ),
      },
      ...typeToDataGridColumnSpec(objectType, disableEdits),
    ];
  }, [disableEdits, makeLinkPath, objectType, path]);
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
        <DataGrid
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
  node: Node;
}> = ({node}) => {
  const opDefQuery = useNodeValue(node);
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
