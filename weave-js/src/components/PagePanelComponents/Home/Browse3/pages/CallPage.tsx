import React, {useMemo} from 'react';

import {Browse2TraceComponent} from '../../Browse2/Browse2TracePage';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './wfInterface/context';

export const CallPage: React.FC<{
  entity: string;
  project: string;
  callId: string;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const call = orm.projectConnection.call(props.callId);
  const params = useMemo(() => {
    return {
      entity: props.entity,
      project: props.project,
      traceId: call.traceID(),
      spanId: props.callId,
    };
  }, [call, props.callId, props.entity, props.project]);
  const title = `${call.spanName()}: ${call.callID()}`;
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
      ]}
    />
  );
};
