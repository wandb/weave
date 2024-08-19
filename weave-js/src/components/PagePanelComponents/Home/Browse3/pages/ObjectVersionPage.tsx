import Box from '@mui/material/Box';
import {useObjectViewEvent} from '@wandb/weave/integrations/analytics/useViewEvents';
import React, {useMemo} from 'react';

import {maybePluralizeWord} from '../../../../../core/util/string';
import {LoadingDots} from '../../../../LoadingDots';
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
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
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
  ObjectVersionSchema,
} from './wfReactInterface/wfDataModelHooksInterface';

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

  const {useRootObjectVersions, useCalls, useRefsData} = useWFHooks();
  const entityName = objectVersion.entity;
  const projectName = objectVersion.project;
  const objectName = objectVersion.objectId;
  const objectVersionIndex = objectVersion.versionIndex;
  const refExtra = objectVersion.refExtra;
  const objectVersions = useRootObjectVersions(entityName, projectName, {
    objectIds: [objectName],
  });
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

  const producingCalls = useCalls(entityName, projectName, {
    outputObjectVersionRefs: [refUri],
  });
  const consumingCalls = useCalls(entityName, projectName, {
    inputObjectVersionRefs: [refUri],
  });
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

  return (
    <SimplePageLayoutWithHeader
      title={objectVersionText(objectName, objectVersionIndex)}
      headerContent={
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
            ...(baseObjectClass
              ? {
                  Category: (
                    <TypeVersionCategoryChip
                      baseObjectClass={baseObjectClass}
                    />
                  ),
                }
              : {}),
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
          label: 'Values',
          content: (
            <ScrollableTabContent>
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
          content:
            baseObjectClass === 'Dataset' ? (
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
