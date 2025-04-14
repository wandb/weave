import {Select} from '@wandb/weave/components/Form/Select';
import React, {useMemo, useState} from 'react';
import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {useWFHooks} from '../pages/wfReactInterface/context';

type SelectMonitorOption = {
  label: string;
  value: string;
};

const OptionLabel = (props: SelectMonitorOption) => {
  const {label} = props;
  return <span className="whitespace-nowrap">{label}</span>;
};

export const SelectMonitor = ({
  entity,
  project,
  value,
  onChange,
}: {
  entity: string;
  project: string;
  value: string;
  onChange: (value: string) => void;
}) => {
  const [monitors, setMonitors] = useState<{label: string; value: string}[]>(
    []
  );
  const [loading, setLoading] = useState(true);
  const {useRootObjectVersions} = useWFHooks();

  const latestMonitors = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Monitor'],
      latestOnly: false,
    },
    undefined,
    false,
    undefined,
    [{field: 'createdAtMs', direction: 'desc'}]
  );

  const placeholder = useMemo(() => {
    if (loading) {
      return 'Loading monitors...';
    }
    if (latestMonitors.result?.length === 0) {
      return 'No monitors found';
    }
    if (latestMonitors.error) {
      return 'Error loading monitors';
    }
    return 'Select a monitor';
  }, [loading, latestMonitors.result, latestMonitors.error]);

  useMemo(() => {
    if (latestMonitors.result) {
      setMonitors(
        latestMonitors.result
          .filter(monitor => monitor.val['active'])
          .map(monitor => ({
            label: `${monitor.val['name']}:v${monitor.versionIndex}`,
            value: `weave:///${entity}/${project}/object/${monitor.objectId}:${monitor.versionHash}`,
          }))
      );
      setLoading(false);
    }
  }, [latestMonitors.result]);

  const selectedValue = useMemo(() => {
    return monitors.find(monitor => monitor.value === value);
  }, [monitors, value]);

  return (
    <Select<{label: string; value: string}, false>
      options={monitors}
      value={selectedValue}
      isDisabled={loading}
      placeholder={placeholder}
      formatOptionLabel={OptionLabel}
      onChange={option => onChange(option?.value ?? '')}
    />
  );
};
