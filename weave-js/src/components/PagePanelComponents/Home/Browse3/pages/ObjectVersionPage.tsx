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
import {useWeaveflowORMContext} from './wfInterface/context';
import {refDictToRefString} from './wfInterface/naive';
import {WFCall, WFObjectVersion, WFOpVersion} from './wfInterface/types';

export const ObjectVersionPage: React.FC<{
  entity: string;
  project: string;
  objectName: string;
  version: string;
  filePath: string;
  refExtra?: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const refExtraParts = props.refExtra ? props.refExtra.split('/') : [];
  const objectVersion = orm.projectConnection.objectVersion(
    refDictToRefString({
      entity: props.entity,
      project: props.project,
      artifactName: props.objectName,
      versionCommitHash: props.version,
      // TODO: We need to get more of these from the URL!
      filePathParts: props.filePath.split('/'),
      refExtraTuples: _.range(0, refExtraParts.length, 2).map(i => ({
        edgeType: refExtraParts[i],
        edgeName: refExtraParts[i + 1],
      })),
    })
  );
  if (!objectVersion) {
    return <CenteredAnimatedLoader />;
  }
  return <ObjectVersionPageInner {...props} objectVersion={objectVersion} />;
};
const ObjectVersionPageInner: React.FC<{
  objectVersion: WFObjectVersion;
}> = ({objectVersion}) => {
  const objectVersionHash = objectVersion.commitHash();
  const entityName = objectVersion.entity();
  const projectName = objectVersion.project();
  const objectName = objectVersion.object().name();
  const objectVersionIndex = objectVersion.versionIndex();
  const objectFilePath = objectVersion.filePath();
  const refExtra = objectVersion.refExtraPath();
  const objectVersionCount = objectVersion.object().objectVersions().length;
  const objectTypeCategory = objectVersion.typeVersion()?.typeCategory();
  const producingCalls = objectVersion.outputFrom().filter(call => {
    return call.opVersion() != null;
  });
  const consumingCalls = objectVersion.inputTo().filter(call => {
    return call.opVersion() != null;
  });
  const refUri = objectVersion.refUri();

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
            ...(producingCalls.length > 0
              ? {
                  [maybePluralizeWord(producingCalls.length, 'Producing Call')]:
                    (
                      <ObjectVersionProducingCallsItem
                        objectVersion={objectVersion}
                      />
                    ),
                }
              : {}),
            ...(consumingCalls.length > 0
              ? {
                  [maybePluralizeWord(producingCalls.length, 'Consuming Call')]:
                    (
                      <ObjectVersionConsumingCallsItem
                        objectVersion={objectVersion}
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
  objectVersion: WFObjectVersion;
}> = props => {
  const producingCalls = props.objectVersion.outputFrom().filter(call => {
    return call.opVersion() != null;
  });
  if (producingCalls.length === 1) {
    const call = producingCalls[0];
    const opVersion = call.opVersion();
    if (opVersion == null) {
      return <>{call.spanName()}</>;
    }
    return (
      <CallLink
        entityName={call.entity()}
        projectName={call.project()}
        opName={opVersion.op().name()}
        callId={call.callID()}
        variant="secondary"
      />
    );
  }
  return (
    <GroupedCalls
      calls={producingCalls}
      partialFilter={{
        outputObjectVersionRefs: [props.objectVersion.refUri()],
      }}
    />
  );
};

const ObjectVersionConsumingCallsItem: React.FC<{
  objectVersion: WFObjectVersion;
}> = props => {
  const consumingCalls = props.objectVersion.inputTo().filter(call => {
    return call.opVersion() != null;
  });
  if (consumingCalls.length === 1) {
    const call = consumingCalls[0];
    const opVersion = call.opVersion();
    if (opVersion == null) {
      return <>{call.spanName()}</>;
    }
    return (
      <CallLink
        entityName={call.entity()}
        projectName={call.project()}
        opName={opVersion.op().name()}
        callId={call.callID()}
        variant="secondary"
      />
    );
  }
  return (
    <GroupedCalls
      calls={consumingCalls}
      partialFilter={{
        inputObjectVersionRefs: [props.objectVersion.refUri()],
      }}
    />
  );
};

export const GroupedCalls: React.FC<{
  calls: WFCall[];
  partialFilter?: WFHighLevelCallFilter;
}> = ({calls, partialFilter}) => {
  const callGroups = useMemo(() => {
    const groups: {
      [key: string]: {
        opVersion: WFOpVersion;
        calls: WFCall[];
      };
    } = {};
    calls.forEach(call => {
      const opVersion = call.opVersion();
      if (opVersion == null) {
        return;
      }

      const key = opVersion.refUri();
      if (groups[key] == null) {
        groups[key] = {
          opVersion,
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
    opVersion: WFOpVersion;
    calls: WFCall[];
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
