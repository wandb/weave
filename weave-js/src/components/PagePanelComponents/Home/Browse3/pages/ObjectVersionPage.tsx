import React, {useMemo} from 'react';

import {constString, opGet} from '../../../../../core';
import {nodeFromExtra} from '../../Browse2/Browse2ObjectVersionItemPage';
import {
  WeaveEditor,
  WeaveEditorSourceContext,
} from '../../Browse2/WeaveEditors';
import {WFHighLevelCallFilter} from './CallsPage';
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
import {useWeaveflowORMContext} from './wfInterface/context';
import {WFCall, WFObjectVersion, WFOpVersion} from './wfInterface/types';

export const ObjectVersionPage: React.FC<{
  entity: string;
  project: string;
  objectName: string;
  version: string;
  refExtra?: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const objectVersion = orm.projectConnection.objectVersion(
    props.objectName,
    props.version
  );
  if (!objectVersion) {
    return <CenteredAnimatedLoader />;
  }
  return <ObjectVersionPageInner {...props} objectVersion={objectVersion} />;
};
const ObjectVersionPageInner: React.FC<{
  objectVersion: WFObjectVersion;
  refExtra?: string;
}> = ({objectVersion, refExtra}) => {
  const objectVersionHash = objectVersion.version();
  const entityName = objectVersion.entity();
  const projectName = objectVersion.project();
  const objectName = objectVersion.object().name();
  const objectVersionIndex = objectVersion.versionIndex();
  const objectVersionCount = objectVersion.object().objectVersions().length;
  const objectTypeCategory = objectVersion.typeVersion().typeCategory();
  const producingCalls = objectVersion.outputFrom().filter(call => {
    return call.opVersion() != null;
  });
  const consumingCalls = objectVersion.inputTo().filter(call => {
    return call.opVersion() != null;
  });
  const baseUri = objectVersion.refUri();

  const itemNode = useMemo(() => {
    const objNode = opGet({uri: constString(baseUri)});
    if (refExtra == null) {
      return objNode;
    }
    const extraFields = refExtra.split('/');
    return nodeFromExtra(objNode, extraFields);
  }, [baseUri, refExtra]);

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
            // TEMP HACK (Tim): Disabling with refExtra is a temporary hack
            // since objectVersion is always an `/obj` path right now which is
            // not correct. There is a more full featured solution here:
            // https://github.com/wandb/weave/pull/1080 that needs to be
            // finished asap. This is just to fix the demo / first internal
            // release.
            ...(refExtra ? {Ref: <span>{baseUri}</span>} : {}),
            // Hide consuming and producing calls since we don't have a
            // good way to look this up yet
            ...(producingCalls.length > 0 && refExtra == null
              ? {
                  'Producing Calls': (
                    <ObjectVersionProducingCallsItem
                      objectVersion={objectVersion}
                    />
                  ),
                }
              : {}),
            ...(consumingCalls.length > 0 && refExtra == null
              ? {
                  'Consuming Calls': (
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
              key={baseUri + refExtra}
              value={{
                entityName,
                projectName,
                objectName,
                objectVersionHash,
                refExtra: refExtra?.split('/'),
              }}>
              <ScrollableTabContent>
                <WeaveEditor objType={objectName} node={itemNode} />
              </ScrollableTabContent>
            </WeaveEditorSourceContext.Provider>
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
  if (producingCalls.length === 0) {
    return <div>-</div>;
  } else if (producingCalls.length === 1) {
    const call = producingCalls[0];
    return (
      <CallLink
        entityName={call.entity()}
        projectName={call.project()}
        callId={call.callID()}
        simpleText={{
          opName: call.spanName(),
          versionIndex: call.opVersion()?.versionIndex() ?? 0,
        }}
      />
    );
  }
  return (
    <ul
      style={{
        paddingInlineStart: '22px',
        margin: 0,
      }}>
      {producingCalls.map(call => {
        return (
          <li key={call.callID()}>
            <CallLink
              entityName={call.entity()}
              projectName={call.project()}
              callId={call.callID()}
              simpleText={{
                opName: call.spanName(),
                versionIndex: call.opVersion()?.versionIndex() ?? 0,
              }}
            />
          </li>
        );
      })}
    </ul>
  );
};

const ObjectVersionConsumingCallsItem: React.FC<{
  objectVersion: WFObjectVersion;
}> = props => {
  const consumingCalls = props.objectVersion.inputTo().filter(call => {
    return call.opVersion() != null;
  });
  return (
    <GroupedCalls
      calls={consumingCalls}
      partialFilter={{
        inputObjectVersions: [
          props.objectVersion.object().name() +
            ':' +
            props.objectVersion.version(),
        ],
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

      const key = opVersion.version();
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
        version={val.opVersion.version()}
        versionIndex={val.opVersion.versionIndex()}
      />{' '}
      [
      <CallsLink
        entity={val.opVersion.entity()}
        project={val.opVersion.project()}
        callCount={val.calls.length}
        filter={{
          opVersions: [
            val.opVersion.op().name() + ':' + val.opVersion.version(),
          ],
          ...(partialFilter ?? {}),
        }}
        neverPeek
      />
      ]
    </>
  );
};
