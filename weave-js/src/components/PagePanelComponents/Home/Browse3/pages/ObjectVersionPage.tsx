import _ from 'lodash';
import React, {useMemo} from 'react';

import {constString, opGet} from '../../../../../core';
import {maybePluralizeWord} from '../../../../../core/util/string';
import {nodeFromExtra} from '../../Browse2/Browse2ObjectVersionItemPage';
import {
  WeaveEditor,
  WeaveEditorSourceContext,
} from '../../Browse2/WeaveEditors';
import {WFHighLevelCallFilter} from './CallsPage/CallsPage';
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
import {UnderConstruction} from './common/UnderConstruction';
import {TabUseDataset} from './TabUseDataset';
import {TabUseModel} from './TabUseModel';
import {TabUseObject} from './TabUseObject';
import {WFCall, WFOpVersion} from './wfInterface/types';
import {
  CallKey,
  CallSchema,
  objectVersionKeyToRefUri,
  ObjectVersionSchema,
  useCall,
  useCalls,
  useObjectVersion,
  useRootObjectVersions,
} from './wfReactInterface/interface';

export const ObjectVersionPage: React.FC<{
  entity: string;
  project: string;
  objectName: string;
  version: string;
  filePath: string;
  refExtra?: string;
}> = props => {
  const objectVersion = useObjectVersion({
    entity: props.entity,
    project: props.project,
    objectId: props.objectName,
    versionHash: props.version,
    path: props.filePath,
    refExtra: props.refExtra,
  });
  if (objectVersion.loading) {
    return <CenteredAnimatedLoader />;
  } else if (objectVersion.result == null) {
    return <div>Object not found</div>;
  }
  return (
    <ObjectVersionPageInner {...props} objectVersion={objectVersion.result} />
  );
};
const ObjectVersionPageInner: React.FC<{
  objectVersion: ObjectVersionSchema;
}> = ({objectVersion}) => {
  const objectVersionHash = objectVersion.versionHash;
  const entityName = objectVersion.entity;
  const projectName = objectVersion.project;
  const objectName = objectVersion.objectId;
  const objectVersionIndex = objectVersion.versionIndex;
  const objectFilePath = objectVersion.path;
  const refExtra = objectVersion.refExtra;
  const objectVersions = useRootObjectVersions(entityName, projectName, {
    objectIds: [objectName],
  });
  const objectVersionCount = (objectVersions.result ?? []).length;
  const objectTypeCategory = objectVersion.category;
  const refUri = objectVersionKeyToRefUri(objectVersion);

  const producingCalls = useCalls(entityName, projectName, {
    outputObjectVersionRefs: [refUri],
  });
  const consumingCalls = useCalls(entityName, projectName, {
    inputObjectVersionRefs: [refUri],
  });

  const itemNode = useMemo(() => {
    const uriParts = refUri.split('#');
    const baseUri = uriParts[0];
    const objNode = opGet({uri: constString(baseUri)});
    if (uriParts.length === 1) {
      return objNode;
    }
    const extraFields = uriParts[1].split('/');
    return nodeFromExtra(objNode, extraFields);
  }, [refUri]);

  return (
    <SimplePageLayoutWithHeader
      title={objectVersionText(objectName, objectVersionIndex)}
      headerContent={
        <SimpleKeyValueTable
          data={{
            [refExtra ? 'Parent Object' : 'Name']: (
              <>
                {objectName} [
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
            ),
            Version: <>{objectVersionIndex}</>,
            ...(objectTypeCategory
              ? {
                  Category: (
                    <TypeVersionCategoryChip
                      typeCategory={objectTypeCategory}
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
            Ref: <span>{refUri}</span>,
            ...((producingCalls.result?.length ?? 0) > 0
              ? {
                  [maybePluralizeWord(
                    producingCalls.result!.length,
                    'Producing Call'
                  )]: (
                    <ObjectVersionProducingCallsItem
                      producingCalls={producingCalls.result!}
                      refUri={refUri}
                    />
                  ),
                }
              : {}),
            ...((consumingCalls.result?.length ?? 0) > 0
              ? {
                  [maybePluralizeWord(
                    consumingCalls.result!.length,
                    'Consuming Call'
                  )]: (
                    <ObjectVersionConsumingCallsItem
                      consumingCalls={consumingCalls.result!}
                      refUri={refUri}
                    />
                  ),
                }
              : {}),
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
            <WeaveEditorSourceContext.Provider
              key={refUri}
              value={{
                entityName,
                projectName,
                objectName,
                objectVersionHash,
                filePath: objectFilePath,
                refExtra: refExtra?.split('/'),
              }}>
              <ScrollableTabContent>
                <WeaveEditor
                  objType={objectName}
                  node={itemNode}
                  disableEdits
                />
              </ScrollableTabContent>
            </WeaveEditorSourceContext.Provider>
          ),
        },
        {
          label: 'Use',
          content:
            objectTypeCategory === 'dataset' ? (
              <TabUseDataset name={objectName} uri={refUri} />
            ) : objectTypeCategory === 'model' ? (
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

        {
          label: 'Boards',
          content: (
            <UnderConstruction
              title="Boards"
              message={
                <>
                  This will show a listing of all boards that reference this
                  object.
                </>
              }
            />
          ),
        },
        {
          label: 'DAG',
          content: (
            <UnderConstruction
              title="Record DAG"
              message={
                <>
                  This page will show a "Record" DAG of Objects and Calls
                  centered at this particular Object Version.
                </>
              }
            />
          ),
        },
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
    const opVersionRef = call.opVersionRef;
    const spanName = call.spanName;
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
    const opVersionRef = call.opVersionRef;
    const spanName = call.spanName;
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
      const opVersionRef = call.opVersionRef;
      if (opVersionRef == null) {
        return;
      }
      const key = opVersionRef;
      if (groups[key] == null) {
        groups[key] = {
          opVersionRef: opVersionRef,
          calls: [],
        };
      }
      groups[key].calls.push(call);
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
  return (
    <>
      <OpVersionLink
        entityName={val.opVersion.entity()}
        projectName={val.opVersion.project()}
        opName={val.opVersion.op().name()}
        version={val.opVersion.commitHash()}
        versionIndex={val.opVersion.versionIndex()}
        variant="secondary"
      />{' '}
      [
      <CallsLink
        entity={val.opVersion.entity()}
        project={val.opVersion.project()}
        callCount={val.calls.length}
        filter={{
          opVersionRefs: [val.opVersion.refUri()],
          ...(partialFilter ?? {}),
        }}
        neverPeek
        variant="secondary"
      />
      ]
    </>
  );
};
