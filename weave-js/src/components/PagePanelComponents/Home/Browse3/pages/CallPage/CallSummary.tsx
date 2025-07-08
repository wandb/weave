import {Button} from '@wandb/weave/components/Button/Button';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import {convertBytes, getJsonPayloadSize} from '@wandb/weave/util';
import _ from 'lodash';
import React, {useMemo} from 'react';

import {parseRefMaybe} from '../../../../../../react';
import {LoadingDots} from '../../../../../LoadingDots';
import {Timestamp} from '../../../../../Timestamp';
import {UserLink} from '../../../../../UserLink';
import {SmallRef} from '../../smallRef/SmallRef';
import {SimpleKeyValueTable} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {CostTable} from './cost';
import {ObjectViewerSection} from './ObjectViewerSection';

const SUMMARY_FIELDS_EXCLUDED_FROM_GENERAL_RENDER = [
  'latency_s',
  'usage',
  'weave',
];

const StorageSizeDisplay: React.FC<{
  size: number;
  loading?: boolean;
}> = ({size, loading}) => {
  if (loading) {
    return <LoadingDots />;
  }

  return (
    <span className="flex items-center gap-2">
      {convertBytes(size)}
      <Tooltip
        content="The size does not include referenced objects, for example, images or audio blob storage."
        trigger={
          <Button icon="info" variant="ghost" size="small" active={false} />
        }
      />
    </span>
  );
};

export const CallSummary: React.FC<{
  call: CallSchema;
}> = ({call}) => {
  const {useCall} = useWFHooks();
  const span = call.rawSpan;
  // Process attributes, only filtering out null values and keys starting with '_'
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

  // TODO: Once the server responds with costs even for unfinished calls,
  // we can remove this second call. See the comment in CallPage.tsx.
  // with `(This results in a second query in CallSummary.tsx)`
  const callWithCosts = useCall({
    key: {
      entity: call.entity,
      project: call.project,
      callId: call.callId,
    },
    includeCosts: true,
  });

  const costData = useMemo(() => {
    return callWithCosts.result?.traceCall?.summary?.weave?.costs;
  }, [callWithCosts.result]);

  const callWithStorageSize = useCall({
    key: {
      entity: call.entity,
      project: call.project,
      callId: call.callId,
    },
    includeTotalStorageSize: true,
  });

  const storageSizeBytesRow = useMemo(() => {
    const storageSpan = callWithStorageSize.result?.rawSpan;

    const size = storageSpan
      ? getJsonPayloadSize(storageSpan.inputs) +
        getJsonPayloadSize(storageSpan.output) +
        getJsonPayloadSize(storageSpan.attributes) +
        getJsonPayloadSize(storageSpan.summary)
      : 0;

    return {
      'Call Storage Size': (
        <StorageSizeDisplay size={size} loading={callWithStorageSize.loading} />
      ),
    };
  }, [callWithStorageSize]);

  const traceStorageSizeBytesRow = useMemo(() => {
    if (call.parentId !== null) {
      return null;
    }

    return {
      'Trace Storage Size': (
        <StorageSizeDisplay
          size={callWithStorageSize.result?.totalStorageSizeBytes ?? 0}
          loading={callWithStorageSize.loading}
        />
      ),
    };
  }, [
    call.parentId,
    callWithStorageSize.result?.totalStorageSizeBytes,
    callWithStorageSize.loading,
  ]);

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
      <div className="mb-16">
        <p
          className="mb-10"
          style={{
            fontWeight: 600,
            marginRight: 10,
            paddingRight: 10,
          }}>
          Details
        </p>
        <SimpleKeyValueTable
          keyColumnWidth={164}
          data={{
            Operation:
              parseRefMaybe(span.name) != null ? (
                <SmallRef objRef={parseRefMaybe(span.name)!} />
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
            Called: (
              <Timestamp value={span.timestamp / 1000} format="relative" />
            ),
            ...(span.summary.latency_s != null && span.status_code !== 'UNSET'
              ? {
                  Latency: span.summary.latency_s.toFixed(3) + 's',
                }
              : {}),
            ...storageSizeBytesRow,
            ...traceStorageSizeBytesRow,
            ...(Object.keys(summary).length > 0 ? summary : {}),
          }}
        />
      </div>
      {Object.keys(attributes).length > 0 && (
        <div className="mb-16">
          <ObjectViewerSection
            title="Attributes"
            data={attributes}
            isExpanded={true}
          />
        </div>
      )}
    </div>
  );
};
