import React from 'react';
import {CallSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {ValueView} from './ValueView';
import {ObjectViewerSection} from './ObjectViewerSection';

type LogEntryProps = {};

const LogEntry = ({entry}: LogEntryProps) => {
  const data = {
    _result: entry.output,
  };
  return (
    <div>
      <ObjectViewerSection title="" data={data} isExpanded={true} />
      {/* <ValueView data={data} isExpanded={true} /> */}
    </div>
  );
};

type CallLogProps = {
  call: CallSchema;
};

export const CallLog = ({call}: CallLogProps) => {
  const log = call.traceCall?.attributes?.weave?.log ?? [];
  console.log({call, log});
  return (
    <div className="p-16">
      {log.map((entry, i) => (
        <LogEntry key={i} entry={entry} />
      ))}
    </div>
  );
};
