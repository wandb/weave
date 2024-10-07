import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent as MaterialDialogContent,
  DialogTitle as MaterialDialogTitle,
} from '@material-ui/core';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import {Button} from '@wandb/weave/components/Button';
import {useObjectViewEvent} from '@wandb/weave/integrations/analytics/useViewEvents';
import React, {useMemo, useState} from 'react';
import styled from 'styled-components';

import {maybePluralizeWord} from '../../../../../core/util/string';
import {Icon, IconName} from '../../../../Icon';
import {LoadingDots} from '../../../../LoadingDots';
import {Tailwind} from '../../../../Tailwind';
import {Tooltip} from '../../../../Tooltip';
import {useClosePeek} from '../context';
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
import {TabUseDataset} from './TabUseDataset';
import {TabUseModel} from './TabUseModel';
import {TabUseObject} from './TabUseObject';
import {useWFHooks} from './wfReactInterface/context';
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
  Model: 'model',
  Dataset: 'table',
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
  if (objectVersion.error) {
    return <NotFoundPanel title={objectVersion.error.reason as string} />;
  } else if (objectVersion.loading) {
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

  const {useRootObjectVersions, useCalls, useRefsData} = useWFHooks();
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
    if (objectVersion.baseObjectClass === 'Dataset') {
      return 'Dataset';
    }
    if (objectVersion.baseObjectClass === 'Model') {
      return 'Model';
    }
    return null;
  }, [objectVersion.baseObjectClass]);
  const refUri = objectVersionKeyToRefUri(objectVersion);

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
      return {_result: viewerData};
    }
    return viewerData;
  }, [viewerData]);

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const isDataset = baseObjectClass === 'Dataset' && refExtra == null;

  return (
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
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="flex-start"
          width="100%">
          <Box flexGrow={1}>
            <SimpleKeyValueTable
              data={{
                [refExtra ? 'Parent Object' : 'Name']: (
                  <>
                    {objectName}{' '}
                    {objectVersions.loading ? (
                      <LoadingDots />
                    ) : (
                      <>
                        [
                        <ObjectVersionsLink
                          entity={entityName}
                          project={projectName}
                          filter={{
                            objectName,
                          }}
                          versionCount={objectVersionCount}
                          neverPeek
                          variant="secondary"
                        />
                        ]
                      </>
                    )}
                  </>
                ),
                Version: <>{objectVersionIndex}</>,
                ...(refExtra
                  ? {
                      Subpath: refExtra,
                    }
                  : {}),
                // 'Type Version': (
                //   <TypeVersionLink
                //     entityName={entityName}
                //     projectName={projectName}
                //     typeName={typeName}
                //     version={typeVersionHash}
                //   />
                // ),
              }}
            />
          </Box>

          <Box mr={1}>
            <Button
              icon="delete"
              variant="ghost"
              onClick={() => setDeleteModalOpen(true)}
            />
          </Box>
          <DeleteModal
            object={objectVersion}
            open={deleteModalOpen}
            onClose={() => setDeleteModalOpen(false)}
          />
        </Stack>
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
                        data={viewerDataAsObject}
                        noHide
                        isExpanded
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
            <Tailwind>
              {baseObjectClass === 'Dataset' ? (
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

const DialogContent = styled(MaterialDialogContent)`
  padding: 0 32px !important;
`;
DialogContent.displayName = 'S.DialogContent';

const DialogTitle = styled(MaterialDialogTitle)`
  padding: 32px 32px 16px 32px !important;

  h2 {
    font-weight: 600;
    font-size: 24px;
    line-height: 30px;
  }
`;
DialogTitle.displayName = 'S.DialogTitle';

const DialogActions = styled(MaterialDialogActions)<{$align: string}>`
  justify-content: ${({$align}) =>
    $align === 'left' ? 'flex-start' : 'flex-end'} !important;
  padding: 32px 32px 32px 32px !important;
`;
DialogActions.displayName = 'S.DialogActions';

const DeleteModal: React.FC<{
  object: ObjectVersionSchema;
  open: boolean;
  onClose: () => void;
}> = ({object, open, onClose}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const objectDelete = useObjectDeleteFunc();
  const closePeek = useClosePeek();

  const [deleteLoading, setDeleteLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deleteTargetStr = object.baseObjectClass ?? 'object';

  const onDelete = () => {
    setDeleteLoading(true);
    objectDelete(object)
      .then(() => {
        onClose();
        closePeek();
      })
      .catch(err => {
        setError(err.message);
      })
      .finally(() => {
        setDeleteLoading(false);
      });
  };

  return (
    <Dialog
      open={open}
      onClose={() => {
        onClose();
        setError(null);
      }}
      maxWidth="xs"
      fullWidth>
      <DialogTitle>Delete {deleteTargetStr}</DialogTitle>
      <DialogContent style={{overflow: 'hidden'}}>
        {error != null ? (
          <p style={{color: 'red'}}>{error}</p>
        ) : (
          <p>Are you sure you want to delete?</p>
        )}
        <span style={{fontSize: '16px', fontWeight: '600'}}>
          {object.objectId}:v{object.versionIndex}
        </span>
      </DialogContent>
      <DialogActions $align="left">
        <Button
          variant="destructive"
          disabled={error != null || deleteLoading}
          onClick={onDelete}>
          {`Delete ${deleteTargetStr}`}
        </Button>
        <Button
          variant="ghost"
          disabled={deleteLoading}
          onClick={() => {
            onClose();
            setError(null);
          }}>
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  );
};
