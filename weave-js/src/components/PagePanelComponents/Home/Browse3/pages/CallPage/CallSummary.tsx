import _ from 'lodash';
import React from 'react';

import {Timestamp} from '../../../../../Timestamp';
import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
import {SimpleKeyValueTable} from '../common/SimplePageLayout';
import {CallSchema} from '../wfReactInterface/interface';

export const CallSummary: React.FC<{
  call: CallSchema;
}> = ({call}) => {
  const span = call.rawSpan;
  const attributes = _.fromPairs(
    Object.entries(span.attributes ?? {}).filter(
      ([k, a]) => !k.startsWith('_') && a != null
    )
  );
  const summary = _.fromPairs(
    Object.entries(span.summary ?? {}).filter(
      ([k, a]) => !k.startsWith('_') && k !== 'latency_s' && a != null
    )
  );

  return (
    <div style={{padding: 8}}>
      <SimpleKeyValueTable
        data={{
          Operation:
            parseRefMaybe(span.name) != null ? (
              <SmallRef
                objRef={parseRefMaybe(span.name)!}
                wfTable="OpVersion"
              />
            ) : (
              span.name
            ),
          Called: <Timestamp value={span.timestamp / 1000} format="relative" />,
          ...(span.summary.latency_s != null
            ? {
                Latency: span.summary.latency_s.toFixed(3) + 's',
              }
            : {}),
          ...(span.exception ? {Exception: span.exception} : {}),
          ...(Object.keys(attributes).length > 0
            ? {Attributes: attributes}
            : {}),
          ...(Object.keys(summary).length > 0 ? {Summary: summary} : {}),
        }}
      />
    </div>
  );
};
