import _ from 'lodash';
import React from 'react';

import {Timestamp} from '../../../../../Timestamp';
import {UserLink} from '../../../../../UserLink';
import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
import {SimpleKeyValueTable} from '../common/SimplePageLayout';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CostTable} from './cost';

const SUMMARY_FIELDS_EXCLUDED_FROM_GENERAL_RENDER = [
  'latency_s',
  'usage',
  'weave',
];

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
      ([k, a]) =>
        // Display all summary fields, but remove usage and latencys stats because we have a separate representations
        !k.startsWith('_') &&
        a != null &&
        !SUMMARY_FIELDS_EXCLUDED_FROM_GENERAL_RENDER.includes(k)
    )
  );
  const costData = call.traceCall?.summary?.weave?.costs;

  return (
    <div className="overflow-auto px-16 pt-12">
      {costData && (
        <div className="mb-16">
          {/* This styling is similar to what is is SimpleKeyValueTable */}
          <p
            className="mb-10"
            style={{
              fontWeight: 600,
              marginRight: 10,
              paddingRight: 10,
            }}>
            Usage
          </p>
          <CostTable costs={costData} />
        </div>
      )}
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
          User: (
            <UserLink
              userId={call.userId}
              placement="bottom-start"
              includeName
            />
          ),
          Called: <Timestamp value={span.timestamp / 1000} format="relative" />,
          ...(span.summary.latency_s != null && span.status_code !== 'UNSET'
            ? {
                Latency: span.summary.latency_s.toFixed(3) + 's',
              }
            : {}),
          ...(Object.keys(attributes).length > 0
            ? {Attributes: attributes}
            : {}),
          ...(Object.keys(summary).length > 0 ? {Summary: summary} : {}),
        }}
      />
    </div>
  );
};
