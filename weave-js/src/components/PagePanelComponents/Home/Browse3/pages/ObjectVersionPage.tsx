import React, {useMemo} from 'react';

import {constString, opGet} from '../../../../../core';
import {nodeFromExtra} from '../../Browse2/Browse2ObjectVersionItemPage';
import {WeaveEditor} from '../../Browse2/WeaveEditors';
import {CallsTable} from './CallsPage';
import {useMakeNewBoard} from './common/hooks';
import {CallLink, ObjectLink, TypeVersionLink} from './common/Links';
import {CenteredAnimatedLoader} from './common/Loader';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {UnderConstruction} from './common/UnderConstruction';
import {useWeaveflowORMContext} from './wfInterface/context';
import {WFObjectVersion} from './wfInterface/types';

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
  const entityName = objectVersion.entity();
  const projectName = objectVersion.project();
  const objectName = objectVersion.object().name();
  const objectVersionHash = objectVersion.version();
  const typeName = objectVersion.typeVersion().type().name();
  const typeVersionHash = objectVersion.typeVersion().version();
  const objecTypeCategory = objectVersion.typeVersion().typeCategory();
  const baseUri = objectVersion.refUri();
  const fullUri = baseUri + (refExtra ?? '');
  const itemNode = useMemo(() => {
    const objNode = opGet({uri: constString(baseUri)});
    if (refExtra == null) {
      return objNode;
    }
    const extraFields = refExtra.split('/');
    return nodeFromExtra(objNode, extraFields);
  }, [baseUri, refExtra]);
  const {onMakeBoard} = useMakeNewBoard(itemNode);

  return (
    <SimplePageLayout
      title={objectName + ' : ' + objectVersionHash}
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
                    <ObjectLink
                      entityName={entityName}
                      projectName={projectName}
                      objectName={objectName}
                    />
                  ),
                  'Type Version': (
                    <>
                      <TypeVersionCategoryChip
                        typeCategory={objecTypeCategory}
                      />

                      <TypeVersionLink
                        entityName={entityName}
                        projectName={projectName}
                        typeName={typeName}
                        version={typeVersionHash}
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
              <WeaveEditor objType={objectName} node={itemNode} />
            </ScrollableTabContent>
          ),
        },
        {
          label: 'Consuming Calls',
          content: (
            <CallsTable
              entity={entityName}
              project={projectName}
              frozenFilter={{
                inputObjectVersions: [objectName + ':' + objectVersionHash],
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
    return (
      <CallLink
        entityName={producingCalls[0].entity()}
        projectName={producingCalls[0].project()}
        callId={producingCalls[0].callID()}
      />
    );
  }
  return (
    <ul>
      {producingCalls.map(call => {
        return (
          <li key={call.callID()}>
            <CallLink
              entityName={call.entity()}
              projectName={call.project()}
              callId={call.callID()}
            />
          </li>
        );
      })}
    </ul>
  );
};
