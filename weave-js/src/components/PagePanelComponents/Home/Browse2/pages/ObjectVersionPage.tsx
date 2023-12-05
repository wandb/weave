// import {Box, CssBaseline, Tab, Tabs, Typography} from '@material-ui/core';
import React, {useMemo} from 'react';

import {constString, opGet} from '../../../../../core';
import {
  Browse2ObjectVersionItemComponent,
  nodeFromExtra,
} from '../Browse2ObjectVersionItemPage';
import {Browse2RootObjectVersionItemParams} from '../CommonLib';
import {WeaveEditor} from '../WeaveEditors';
import {useMakeNewBoard} from './common/hooks';
import {CallLink, ObjectLink, TypeVersionLink} from './common/Links';
import {
  ScrollableTabContent,
  SimpleKeyValueTable,
  SimplePageLayout,
} from './common/SimplePageLayout';
import {useObjectVersionTypeInfo} from './interface/dataModel';
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
  const {onMakeBoard, isGenerating} = useMakeNewBoard(itemNode);

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
          label: '(TODO) Compare',
          onClick: () => {
            console.log('(TODO) Compare');
          },
        },
        {
          label: '(TODO) Process with Function',
          onClick: () => {
            console.log('(TODO) Process with Function');
          },
        },
        {
          label: '(TODO) Add to Hub',
          onClick: () => {
            console.log('(TODO) Add to Hub');
          },
        },
      ]}
      tabs={[
        {
          label: 'Values',
          content: (
            <ScrollableTabContent>
              <WeaveEditor objType={props.objectName} node={itemNode} />
            </ScrollableTabContent>
          ),
        },
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
                    <TypeVersionLink
                      typeName={objectVersion.typeVersion().type().name()}
                      version={objectVersion.typeVersion().version()}
                    />
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
          label: 'Consuming Calls',
          content: <div>Calls</div>,
        },

        {
          label: 'Boards',
          content: <div>Boards</div>,
        },
        {
          label: 'DAG',
          content: <div>DAG</div>,
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
