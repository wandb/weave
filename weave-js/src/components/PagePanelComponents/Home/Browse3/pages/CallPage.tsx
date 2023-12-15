import React, {useMemo} from 'react';

import {Browse2TraceComponent} from '../../Browse2/Browse2TracePage';
import {CallsTable} from './CallsPage';
import {CenteredAnimatedLoader} from './common/Loader';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './wfInterface/context';
import {WFCall} from './wfInterface/types';

export const CallPage: React.FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const call = orm.projectConnection.call(props.callId);
  if (!call) {
    return <CenteredAnimatedLoader />;
  }
  return <CallPageInner {...props} call={call} />;
};

const CallPageInner: React.FC<{
  call: WFCall;
}> = ({call}) => {
  const entityName = call.entity();
  const projectName = call.project();
  const traceId = call.traceID();
  const callId = call.callID();
  const spanName = call.spanName();

  const params = useMemo(() => {
    return {
      entity: entityName,
      project: projectName,
      traceId,
      spanId: callId,
    };
  }, [entityName, projectName, traceId, callId]);
  const title = `${spanName}: ${callId}`;
  return (
    <SimplePageLayout
      title={title}
      menuItems={[
        {
          label: '(Under Construction) Open in Board',
          onClick: () => {
            console.log('TODO: Open in Board');
          },
        },
        {
          label: '(Under Construction) Compare',
          onClick: () => {
            console.log('TODO: Compare');
          },
        },
      ]}
      tabs={[
        {
          label: 'Trace',
          content: <Browse2TraceComponent params={params} />,
        },
        {
          label: 'Calls',
          content: (
            <CallsTable
              entity={entityName}
              project={projectName}
              frozenFilter={{
                parentId: callId,
              }}
            />
          ),
        },
      ]}
    />
  );
};
