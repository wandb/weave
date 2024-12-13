import {Popover, Typography} from '@mui/material';
import Box from '@mui/material/Box';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {useObjectViewEvent} from '@wandb/weave/integrations/analytics/useViewEvents';
import React, {useCallback, useMemo, useState} from 'react';
import {Link} from 'react-router-dom';

import {maybePluralizeWord} from '../../../../../core/util/string';
import {Button} from '../../../../Button';
import {Icon, IconName} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Tailwind} from '../../../../Tailwind';
import {Tooltip} from '../../../../Tooltip';
import {useWeaveflowCurrentRouteContext} from '../context';
import {NotFoundPanel} from '../NotFoundPanel';
import {CustomWeaveTypeProjectContext} from '../typeViews/CustomWeaveTypeDispatcher';
import {WeaveCHTableSourceRefContext} from './CallPage/DataTableView';
import {ObjectViewerSection} from './CallPage/ObjectViewerSection';
import {WFHighLevelCallFilter} from './CallsPage/callsTableFilter';
import {
  CallLink,
  CallsLink,
  ObjectVersionsLink,
  objectVersionText,
  OpVersionLink,
} from './common/Links';
import {CenteredAnimatedLoader} from './common/Loader';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayoutWithHeader,
} from './common/SimplePageLayout';
import {DatasetEditContext} from './DatasetEditContext';
import {EvaluationLeaderboardTab} from './LeaderboardTab';
import {TabPrompt} from './TabPrompt';
import {TabUseDataset} from './TabUseDataset';
import {TabUseModel} from './TabUseModel';
import {TabUseObject} from './TabUseObject';
import {TabUsePrompt} from './TabUsePrompt';
import {KNOWN_BASE_OBJECT_CLASSES} from './wfReactInterface/constants';
import {useWFHooks} from './wfReactInterface/context';
import {
  TableInsertSpec,
  TablePopSpec,
  TableUpdateSpec,
} from './wfReactInterface/traceServerClientTypes';
import {
  objectVersionKeyToRefUri,
  refUriToOpVersionKey,
} from './wfReactInterface/utilities';
import {
  CallSchema,
  KnownBaseObjectClassType,
  ObjectVersionSchema,
} from './wfReactInterface/wfDataModelHooksInterface';

type ObjectIconProps = {
  baseObjectClass: KnownBaseObjectClassType;
};
const OBJECT_ICONS: Record<KnownBaseObjectClassType, IconName> = {
  Prompt: 'forum-chat-bubble',
  Model: 'model',
  Dataset: 'table',
  Evaluation: 'baseline-alt',
  Leaderboard: 'benchmark-square',
  Scorer: 'type-number-alt',
  ActionSpec: 'rocket-launch',
  AnnotationSpec: 'forum-chat-bubble',
};
const ObjectIcon = ({baseObjectClass}: ObjectIconProps) => {
  if (baseObjectClass in OBJECT_ICONS) {
    const iconName = OBJECT_ICONS[baseObjectClass];
    return (
      <Tooltip
        trigger={
          <div className="flex h-22 w-22 items-center justify-center rounded-full bg-moon-300/[0.48] text-moon-600">
            <Icon width={14} height={14} name={iconName} />
          </div>
        }
        content={baseObjectClass}
      />
    );
  }
  return null;
};

export const ObjectVersionPage: React.FC<{
  entity: string;
  project: string;
  objectName: string;
  version: string;
  filePath: string;
  refExtra?: string;
}> = props => {
  const {useObjectVersion} = useWFHooks();

  const objectVersion = useObjectVersion({
    // Blindly assume this is weave object?
    scheme: 'weave',
    entity: props.entity,
    project: props.project,
    weaveKind: 'object',
    objectId: props.objectName,
    versionHash: props.version,
    path: props.filePath,
    refExtra: props.refExtra,
  });
  if (objectVersion.loading) {
    return <CenteredAnimatedLoader />;
  } else if (objectVersion.result == null) {
    return <NotFoundPanel title="Object not found" />;
  }
  return (
    <ObjectVersionPageInner {...props} objectVersion={objectVersion.result} />
  );
};
const ObjectVersionPageInner: React.FC<{
  objectVersion: ObjectVersionSchema;
}> = ({objectVersion}) => {
  useObjectViewEvent(objectVersion);

  const {
    useRootObjectVersions,
    useCalls,
    useRefsData,
    useTableUpdate,
    useObjCreate,
  } = useWFHooks();
  const entityName = objectVersion.entity;
  const projectName = objectVersion.project;
  const objectName = objectVersion.objectId;
  const objectVersionIndex = objectVersion.versionIndex;
  const refExtra = objectVersion.refExtra;
  const objectVersions = useRootObjectVersions(
    entityName,
    projectName,
    {
      objectIds: [objectName],
    },
    undefined,
    true
  );
  const objectVersionCount = (objectVersions.result ?? []).length;
  const baseObjectClass = useMemo(() => {
    const s = objectVersion.baseObjectClass;
    return KNOWN_BASE_OBJECT_CLASSES.includes(s as KnownBaseObjectClassType)
      ? (s as KnownBaseObjectClassType)
      : null;
  }, [objectVersion.baseObjectClass]);
  const refUri = objectVersionKeyToRefUri(objectVersion);

  const showPromptTab = objectVersion.val._class_name === 'EasyPrompt';

  const minimalColumns = useMemo(() => {
    return ['id', 'op_name', 'project_id'];
  }, []);
  const producingCalls = useCalls(
    entityName,
    projectName,
    {
      outputObjectVersionRefs: [refUri],
    },
    undefined,
    undefined,
    undefined,
    undefined,
    minimalColumns
  );

  const consumingCalls = useCalls(
    entityName,
    projectName,
    {
      inputObjectVersionRefs: [refUri],
    },
    undefined,
    undefined,
    undefined,
    undefined,
    minimalColumns
  );

  const showCallsTab =
    !(producingCalls.loading || consumingCalls.loading) &&
    (producingCalls.result?.length ?? 0) +
      (consumingCalls.result?.length ?? 0) >
      0;
  const data = useRefsData([refUri]);
  const viewerData = useMemo(() => {
    if (data.loading) {
      return {};
    }
    return data.result?.[0] ?? {};
  }, [data.loading, data.result]);

  const viewerDataAsObject = useMemo(() => {
    const dataIsPrimitive =
      typeof viewerData !== 'object' ||
      viewerData === null ||
      Array.isArray(viewerData);
    if (dataIsPrimitive) {
      // _result is a special key that is automatically removed by the
      // ObjectViewerSection component.
      return {
        _result: viewerData,
      };
    }
    return viewerData;
  }, [viewerData]);

  const isDataset = baseObjectClass === 'Dataset' && refExtra == null;
  const [isEditing, setIsEditing] = useState(false);
  const [publishAnchorEl, setPublishAnchorEl] = useState<HTMLElement | null>(
    null
  );

  const [editedCellsMap, setEditedCellsMap] = useState<Map<string, any>>(
    new Map()
  );
  const [editedRows, setEditedRows] = useState<Map<string, any>>(new Map());
  const [deletedRows, setDeletedRows] = useState<number[]>([]);
  const [addedRows, setAddedRows] = useState<Map<string, any>>(new Map());

  const router = useWeaveflowCurrentRouteContext();

  const handleEditClick = useCallback(() => {
    setIsEditing(true);
  }, []);

  const handleCancelClick = useCallback(() => {
    setIsEditing(false);
    setEditedCellsMap(new Map());
    setEditedRows(new Map());
    setDeletedRows([]);
  }, []);

  const handlePublishClick = useCallback(
    (event: React.MouseEvent<HTMLElement>) => {
      if (
        editedCellsMap.size > 0 ||
        deletedRows.length > 0 ||
        addedRows.size > 0
      ) {
        setPublishAnchorEl(event.currentTarget);
      }
    },
    [editedCellsMap, deletedRows, addedRows]
  );

  const handlePublishClose = () => {
    setPublishAnchorEl(null);
  };

  const processRowUpdate = useCallback((newRow: any, oldRow: any) => {
    const changedField = Object.keys(newRow).find(
      key => newRow[key] !== oldRow[key] && key !== 'id'
    );

    if (changedField) {
      const rowKey = `${newRow.id}`;
      if (rowKey.startsWith('new-')) {
        setAddedRows(prev => {
          const updatedMap = new Map(prev);
          updatedMap.set(rowKey, newRow);
          return updatedMap;
        });
      } else {
        setEditedCellsMap(prev => {
          const existingEdits = prev.get(rowKey) || {};
          const updatedMap = new Map(prev);
          updatedMap.set(rowKey, {
            ...existingEdits,
            [changedField]: newRow[changedField],
          });
          return updatedMap;
        });
        setEditedRows(prev => {
          const updatedMap = new Map(prev);
          updatedMap.set(rowKey, newRow);
          return updatedMap;
        });
      }
    }
    return newRow;
  }, []);

  const cleanRow = (row: any) => {
    return Object.fromEntries(
      Object.entries(row).filter(([key]) => !['id', '_index'].includes(key))
    );
  };

  // Function to convert edited cells to TableUpdateSpec
  const convertEditsToTableUpdateSpec = useCallback(() => {
    const updates: TableUpdateSpec[] = [];
    editedRows.forEach((editedRow, rowKey) => {
      const rowIndex = editedRow._index;
      if (rowIndex !== undefined) {
        const popSpec: TablePopSpec = {
          pop: {
            index: rowIndex,
          },
        };
        const insertSpec: TableInsertSpec = {
          insert: {
            index: rowIndex,
            row: cleanRow(editedRow),
          },
        };
        updates.push(popSpec);
        updates.push(insertSpec);
      }
    });
    // sort the indices of deleted rows in descending order
    // and then add updates to remove the deleted rows
    deletedRows.sort((a, b) => b - a);
    deletedRows.forEach(rowIndex => {
      const popSpec: TablePopSpec = {
        pop: {
          index: rowIndex,
        },
      };
      updates.push(popSpec);
    });
    // add the added rows to the updates
    Array.from(addedRows.values())
      .reverse()
      .forEach(row => {
        const appendSpec: TableInsertSpec = {
          insert: {
            index: 0,
            row: cleanRow(row),
          },
        };
        updates.push(appendSpec);
      });
    return updates;
  }, [editedRows, deletedRows, addedRows]);

  const tableUpdate = useTableUpdate();
  const objCreate = useObjCreate();

  const projectId = `${entityName}/${projectName}`;
  const originalTableDigest = viewerDataAsObject?.rows?.split('/').pop() ?? '';

  const handlePublish = useCallback(async () => {
    setIsEditing(false);
    setPublishAnchorEl(null);
    const tableUpdateSpecs = convertEditsToTableUpdateSpec();
    const tableUpdateResp = await tableUpdate(
      projectId,
      originalTableDigest,
      tableUpdateSpecs
    );
    const tableRef = `weave:///${projectId}/table/${tableUpdateResp.digest}`;
    const newObjVersion = await objCreate(projectId, objectName, {
      ...objectVersion.val,
      rows: tableRef,
    });

    const url = router.objectVersionUIUrl(
      entityName,
      projectName,
      objectName,
      newObjVersion,
      undefined,
      refExtra
    );

    toast(
      <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
        <Icon name="checkmark" width={20} height={20} />
        Published{' '}
        <Link
          to={url}
          style={{
            color: 'rgb(94, 234, 212)',
            textDecoration: 'none',
            fontFamily: 'Inconsolata',
            fontWeight: 600,
          }}>
          {objectName}:v{objectVersionCount}
        </Link>
      </div>
    );
  }, [
    refExtra,
    router,
    objectName,
    objectVersionCount,
    objectVersion.val,
    convertEditsToTableUpdateSpec,
    projectId,
    objCreate,
    tableUpdate,
    originalTableDigest,
    entityName,
    projectName,
  ]);
  const isEvaluation = baseObjectClass === 'Evaluation' && refExtra == null;
  const evalHasCalls = (consumingCalls.result?.length ?? 0) > 0;
  const evalHasCallsLoading = consumingCalls.loading;

  if (isEvaluation && evalHasCallsLoading) {
    return <CenteredAnimatedLoader />;
  }

  return (
    <DatasetEditContext.Provider
      value={{
        editedCellsMap,
        setEditedCellsMap,
        editedRows,
        setEditedRows,
        processRowUpdate,
        deletedRows,
        setDeletedRows,
        addedRows,
        setAddedRows,
      }}>
      <SimplePageLayoutWithHeader
        title={
          <Tailwind>
            <div className="flex items-center gap-8">
              {baseObjectClass && (
                <ObjectIcon baseObjectClass={baseObjectClass} />
              )}
              {objectVersionText(objectName, objectVersionIndex)}
            </div>
          </Tailwind>
        }
        headerContent={
          <Tailwind>
            <div className="flex w-full items-start justify-between">
              <div className="grid auto-cols-max grid-flow-col gap-[16px] text-[14px]">
                <div className="block">
                  <p className="text-moon-500">Name</p>
                  <div className="flex items-center">
                    <ObjectVersionsLink
                      entity={entityName}
                      project={projectName}
                      filter={{objectName}}
                      versionCount={objectVersionCount}
                      neverPeek
                      variant="secondary">
                      <div className="group flex items-center font-semibold">
                        <span>{objectName}</span>
                        {objectVersions.loading ? (
                          <LoadingDots />
                        ) : (
                          <span className="ml-[4px]">
                            ({objectVersionCount} version
                            {objectVersionCount !== 1 ? 's' : ''})
                          </span>
                        )}
                        <Icon
                          name="forward-next"
                          width={16}
                          height={16}
                          className="ml-[2px] opacity-0 group-hover:opacity-100"
                        />
                      </div>
                    </ObjectVersionsLink>
                  </div>
                </div>
                <div className="block">
                  <p className="text-moon-500">Version</p>
                  <p>{objectVersionIndex}</p>
                </div>
                {refExtra && (
                  <div className="block">
                    <p className="text-moon-500">Subpath</p>
                    <p>{refExtra}</p>
                  </div>
                )}
              </div>
              {isDataset && (
                <>
                  {isEditing ? (
                    <div className="flex gap-8">
                      <Typography
                        variant="body2"
                        sx={{
                          color: 'text.secondary',
                          display: 'flex',
                          alignItems: 'center',
                          fontSize: '14px',
                          fontFamily: 'Source Sans Pro',
                        }}>
                        Editing dataset
                        <Icon name="pencil-edit" width={14} height={14} />
                      </Typography>
                      <Button
                        title="Cancel"
                        variant="ghost"
                        size="medium"
                        icon="close"
                        onClick={handleCancelClick}>
                        Cancel
                      </Button>
                      <Button
                        title="Publish"
                        size="medium"
                        variant="primary"
                        icon="checkmark"
                        onClick={handlePublishClick}
                        disabled={
                          editedCellsMap.size === 0 &&
                          deletedRows.length === 0 &&
                          addedRows.size === 0
                        }>
                        Publish
                      </Button>
                    </div>
                  ) : (
                    <Button
                      title="Edit"
                      variant="secondary"
                      size="medium"
                      icon="pencil-edit"
                      onClick={handleEditClick}>
                      Edit
                    </Button>
                  )}
                </>
              )}
            </div>
          </Tailwind>
        }
        // menuItems={[
        //   {
        //     label: 'Open in Board',
        //     onClick: () => {
        //       onMakeBoard();
        //     },
        //   },
        //   {
        //     label: '(Under Construction) Compare',
        //     onClick: () => {
        //       console.log('(Under Construction) Compare');
        //     },
        //   },
        //   {
        //     label: '(Under Construction) Process with Function',
        //     onClick: () => {
        //       console.log('(Under Construction) Process with Function');
        //     },
        //   },
        //   {
        //     label: '(Coming Soon) Add to Hub',
        //     onClick: () => {
        //       console.log('(Under Construction) Add to Hub');
        //     },
        //   },
        // ]}
        tabs={[
          ...(showPromptTab
            ? [
                {
                  label: 'Prompt',
                  content: (
                    <ScrollableTabContent>
                      {data.loading ? (
                        <CenteredAnimatedLoader />
                      ) : (
                        <TabPrompt
                          entity={entityName}
                          project={projectName}
                          data={viewerDataAsObject}
                        />
                      )}
                    </ScrollableTabContent>
                  ),
                },
              ]
            : []),
          ...(isEvaluation && evalHasCalls
            ? [
                {
                  label: 'Leaderboard',
                  content: (
                    <EvaluationLeaderboardTab
                      entity={entityName}
                      project={projectName}
                      evaluationObjectName={objectName}
                      evaluationObjectVersion={objectVersion.versionHash}
                    />
                  ),
                },
              ]
            : []),
          {
            label: isDataset ? 'Rows' : 'Values',
            content: (
              <ScrollableTabContent sx={isDataset ? {p: 0} : {}}>
                <Box
                  sx={{
                    flex: '0 0 auto',
                    height: '100%',
                  }}>
                  {data.loading ? (
                    <CenteredAnimatedLoader />
                  ) : (
                    <WeaveCHTableSourceRefContext.Provider value={refUri}>
                      <CustomWeaveTypeProjectContext.Provider
                        value={{entity: entityName, project: projectName}}>
                        <ObjectViewerSection
                          title=""
                          objectId={objectName}
                          data={viewerDataAsObject}
                          noHide
                          isExpanded
                          isEditing={isEditing}
                        />
                      </CustomWeaveTypeProjectContext.Provider>
                    </WeaveCHTableSourceRefContext.Provider>
                  )}
                </Box>
              </ScrollableTabContent>
            ),
          },
          {
            label: 'Use',
            content: (
              <ScrollableTabContent>
                <Tailwind>
                  {baseObjectClass === 'Prompt' ? (
                    <TabUsePrompt
                      name={objectName}
                      uri={refUri}
                      entityName={entityName}
                      projectName={projectName}
                      data={viewerDataAsObject}
                    />
                  ) : baseObjectClass === 'Dataset' ? (
                    <TabUseDataset
                      name={objectName}
                      uri={refUri}
                      versionIndex={objectVersionIndex}
                    />
                  ) : baseObjectClass === 'Model' ? (
                    <TabUseModel
                      name={objectName}
                      uri={refUri}
                      projectName={projectName}
                    />
                  ) : (
                    <TabUseObject name={objectName} uri={refUri} />
                  )}
                </Tailwind>
              </ScrollableTabContent>
            ),
          },

          // {
          //   label: 'Metadata',
          //   content: (
          //     <ScrollableTabContent>
          //       <SimpleKeyValueTable
          //         data={{
          //           Object: (
          //             <ObjectLink
          //               entityName={entityName}
          //               projectName={projectName}
          //               objectName={objectName}
          //             />
          //           ),
          //           'Type Version': (
          //             <>
          //               <TypeVersionCategoryChip
          //                 typeCategory={objectTypeCategory}
          //               />

          //               <TypeVersionLink
          //                 entityName={entityName}
          //                 projectName={projectName}
          //                 typeName={typeName}
          //                 version={typeVersionHash}
          //               />
          //             </>
          //           ),
          //           Ref: fullUri,
          //           'Producing Calls': (
          //             <ObjectVersionProducingCallsItem
          //               objectVersion={objectVersion}
          //             />
          //           ),
          //         }}
          //       />
          //     </ScrollableTabContent>
          //   ),
          // },
          // {
          //   label: 'Consuming Calls',
          //   content: (
          //     <CallsTable
          //       entity={entityName}
          //       project={projectName}
          //       frozenFilter={{
          //         inputObjectVersions: [objectName + ':' + objectVersionHash],
          //       }}
          //     />
          //   ),
          // },
          ...(showCallsTab
            ? [
                {
                  label: 'Calls',
                  content: (
                    <Box sx={{p: 2}}>
                      <SimpleKeyValueTable
                        data={{
                          ...(producingCalls.result!.length > 0
                            ? {
                                [maybePluralizeWord(
                                  producingCalls.result!.length,
                                  'Producing Call'
                                )]: (
                                  <ObjectVersionProducingCallsItem
                                    producingCalls={producingCalls.result ?? []}
                                    refUri={refUri}
                                  />
                                ),
                              }
                            : {}),
                          ...(consumingCalls.result!.length
                            ? {
                                [maybePluralizeWord(
                                  consumingCalls.result!.length,
                                  'Consuming Call'
                                )]: (
                                  <ObjectVersionConsumingCallsItem
                                    consumingCalls={consumingCalls.result ?? []}
                                    refUri={refUri}
                                  />
                                ),
                              }
                            : {}),
                        }}
                      />
                    </Box>
                  ),
                },
              ]
            : []),
        ]}
      />
      <Popover
        open={Boolean(publishAnchorEl)}
        anchorEl={publishAnchorEl}
        onClose={handlePublishClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        sx={{
          '& .MuiPopover-paper': {
            marginTop: '8px',
            marginRight: '8px',
          },
        }}>
        <Box
          sx={{
            p: 3,
            width: 300,
            bgcolor: 'background.paper',
            borderRadius: '8px',
            '& .MuiTypography-root': {
              fontFamily: 'Source Sans Pro',
            },
          }}>
          <Typography variant="h6" sx={{mb: 2, fontWeight: 600}}>
            Confirm
          </Typography>
          <Typography sx={{mb: 2}}>
            Publish changes to a new version of{' '}
            <code
              style={{
                fontFamily: 'Inconsolata',
                fontWeight: 600,
                backgroundColor: 'rgba(0, 0, 0, 0.04)',
                padding: '2px 4px',
                borderRadius: '4px',
              }}>
              {objectName}
            </code>
            ?
          </Typography>
          <Box sx={{display: 'flex', justifyContent: 'flex-end', gap: 2}}>
            <Button variant="ghost" onClick={handlePublishClose}>
              Not yet
            </Button>
            <Button
              icon="checkmark"
              variant="primary"
              onClick={() => {
                handlePublish();
                handlePublishClose();
              }}>
              Publish
            </Button>
          </Box>
        </Box>
      </Popover>
    </DatasetEditContext.Provider>
  );
};

const ObjectVersionProducingCallsItem: React.FC<{
  producingCalls: CallSchema[];
  refUri: string;
}> = props => {
  if (props.producingCalls.length === 1) {
    const call = props.producingCalls[0];
    const {opVersionRef, spanName} = call;
    if (opVersionRef == null) {
      return <>{spanName}</>;
    }
    return (
      <CallLink
        entityName={call.entity}
        projectName={call.project}
        opName={spanName}
        callId={call.callId}
        variant="secondary"
      />
    );
  }
  return (
    <GroupedCalls
      calls={props.producingCalls}
      partialFilter={{
        outputObjectVersionRefs: [props.refUri],
      }}
    />
  );
};
const ObjectVersionConsumingCallsItem: React.FC<{
  consumingCalls: CallSchema[];
  refUri: string;
}> = props => {
  if (props.consumingCalls.length === 1) {
    const call = props.consumingCalls[0];
    const {opVersionRef, spanName} = call;
    if (opVersionRef == null) {
      return <>{spanName}</>;
    }
    return (
      <CallLink
        entityName={call.entity}
        projectName={call.project}
        opName={spanName}
        callId={call.callId}
        variant="secondary"
      />
    );
  }
  return (
    <GroupedCalls
      calls={props.consumingCalls}
      partialFilter={{
        inputObjectVersionRefs: [props.refUri],
      }}
    />
  );
};

export const GroupedCalls: React.FC<{
  calls: CallSchema[];
  partialFilter?: WFHighLevelCallFilter;
}> = ({calls, partialFilter}) => {
  const callGroups = useMemo(() => {
    const groups: {
      [key: string]: {
        opVersionRef: string;
        calls: CallSchema[];
      };
    } = {};
    calls.forEach(call => {
      const {opVersionRef} = call;
      if (opVersionRef == null) {
        return;
      }
      if (groups[opVersionRef] == null) {
        groups[opVersionRef] = {
          opVersionRef,
          calls: [],
        };
      }
      groups[opVersionRef].calls.push(call);
    });
    return groups;
  }, [calls]);

  if (calls.length === 0) {
    return <div>-</div>;
  } else if (Object.keys(callGroups).length === 1) {
    const key = Object.keys(callGroups)[0];
    const val = callGroups[key];
    return <OpVersionCallsLink val={val} partialFilter={partialFilter} />;
  }
  return (
    <ul
      style={{
        margin: 0,
        paddingInlineStart: '22px',
      }}>
      {Object.entries(callGroups).map(([key, val], ndx) => {
        return (
          <li key={key}>
            <OpVersionCallsLink val={val} partialFilter={partialFilter} />
          </li>
        );
      })}
    </ul>
  );
};

const OpVersionCallsLink: React.FC<{
  val: {
    opVersionRef: string;
    calls: CallSchema[];
  };
  partialFilter?: WFHighLevelCallFilter;
}> = ({val, partialFilter}) => {
  const {useOpVersion} = useWFHooks();
  const opVersion = useOpVersion(refUriToOpVersionKey(val.opVersionRef));
  if (opVersion.loading) {
    return null;
  } else if (opVersion.result == null) {
    return null;
  }
  return (
    <>
      <OpVersionLink
        entityName={opVersion.result.entity}
        projectName={opVersion.result.project}
        opName={opVersion.result.opId}
        version={opVersion.result.versionHash}
        versionIndex={opVersion.result.versionIndex}
        variant="secondary"
      />{' '}
      [
      <CallsLink
        entity={opVersion.result.entity}
        project={opVersion.result.project}
        callCount={val.calls.length}
        filter={{
          opVersionRefs: [val.opVersionRef],
          ...(partialFilter ?? {}),
        }}
        neverPeek
        variant="secondary"
      />
      ]
    </>
  );
};
