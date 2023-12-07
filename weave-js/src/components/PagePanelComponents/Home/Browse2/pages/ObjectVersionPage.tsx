import React, {useMemo} from 'react';

import {constString, opGet} from '../../../../../core';
import {nodeFromExtra} from '../Browse2ObjectVersionItemPage';
import {WeaveEditor} from '../WeaveEditors';
import {CallsTable} from './CallsPage';
import {useMakeNewBoard} from './common/hooks';
import {CallLink, ObjectLink, TypeVersionLink} from './common/Links';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {UnderConstruction} from './common/UnderConstruction';
import {useWeaveflowORMContext} from './interface/wf/context';
import {WFObjectVersion} from './interface/wf/types';

export const ObjectVersionPage: React.FC<{
  entity: string;
  project: string;
  objectName: string;
  version: string;
  refExtra?: string;
}> = props => {
  const orm = useWeaveflowORMContext();
  const objectVersion = orm.projectConnection.objectVersion(
    props.objectName,
    props.version
  );
  const baseUri = objectVersion.refUri();
  const fullUri = baseUri + (props.refExtra ?? '');
  const itemNode = useMemo(() => {
    const objNode = opGet({uri: constString(baseUri)});
    if (props.refExtra == null) {
      return objNode;
    }
    const extraFields = props.refExtra.split('/');
    return nodeFromExtra(objNode, extraFields);
  }, [baseUri, props.refExtra]);
  const {onMakeBoard} = useMakeNewBoard(itemNode);

  return (
    <SimplePageLayout
      title={props.objectName + ' : ' + props.version}
      menuItems={[
        {
          label: 'Open in Board',
          onClick: () => {
            onMakeBoard();
          },
        },
        {
          label: '(Under Construction) Compare',
          onClick: () => {
            console.log('(Under Construction) Compare');
          },
        },
        {
          label: '(Under Construction) Process with Function',
          onClick: () => {
            console.log('(Under Construction) Process with Function');
          },
        },
        {
          label: '(Coming Soon) Add to Hub',
          onClick: () => {
            console.log('(Under Construction) Add to Hub');
          },
        },
      ]}
      tabs={[
        {
          label: 'Overview',
          content: (
            <ScrollableTabContent>
              <SimpleKeyValueTable
                data={{
                  Object: (
                    <ObjectLink objectName={objectVersion.object().name()} />
                  ),
                  'Type Version': (
                    <>
                      <TypeVersionCategoryChip
                        typeCategory={objectVersion
                          .typeVersion()
                          .typeCategory()}
                      />

                      <TypeVersionLink
                        typeName={objectVersion.typeVersion().type().name()}
                        version={objectVersion.typeVersion().version()}
                      />
                    </>
                  ),
                  Ref: fullUri,
                  'Producing Calls': (
                    <ObjectVersionProducingCallsItem
                      objectVersion={objectVersion}
                    />
                  ),
                }}
              />
            </ScrollableTabContent>
          ),
        },
        {
          label: 'Values',
          content: (
            <ScrollableTabContent>
              <WeaveEditor objType={props.objectName} node={itemNode} />
            </ScrollableTabContent>
          ),
        },
        {
          label: 'Consuming Calls',
          content: (
            <CallsTable
              entity={props.entity}
              project={props.project}
              frozenFilter={{
                inputObjectVersions: [props.objectName + ':' + props.version],
              }}
            />
          ),
        },

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
    return <CallLink callId={producingCalls[0].callID()} />;
  }
  return (
    <ul>
      {producingCalls.map(call => {
        return (
          <li key={call.callID()}>
            <CallLink callId={call.callID()} />
          </li>
        );
      })}
    </ul>
  );
};
