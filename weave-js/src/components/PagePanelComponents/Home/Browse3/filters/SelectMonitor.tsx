import {Select} from '@wandb/weave/components/Form/Select';
import {IconNames} from '@wandb/weave/components/Icon';
import React, {useMemo, useState} from 'react';

import {SortBy} from '../pages/wfReactInterface/traceServerClientTypes';
import {useRootObjectVersions} from '../pages/wfReactInterface/tsDataModelHooks';
import {ObjectVersionFilter} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {SmallRefIcon} from '../smallRef/SmallRefIcon';

type SelectMonitorOption = {
  label: string;
  value: string;
};

const OptionLabel = (props: SelectMonitorOption) => {
  const {label} = props;
  return (
    <span className="flex items-center gap-4 whitespace-nowrap">
      <SmallRefIcon icon={IconNames.JobAutomation} />
      {label}
    </span>
  );
};

const OBJECT_VERSIONS_SORT_BY: SortBy[] = [
  {field: 'createdAtMs', direction: 'desc'},
];

const OBJECT_VERSIONS_FILTER: ObjectVersionFilter = {
  baseObjectClasses: ['Monitor'],
  latestOnly: true,
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

  const monitorsResult = useRootObjectVersions({
    entity,
    project,
    filter: OBJECT_VERSIONS_FILTER,
    metadataOnly: false,
    sortBy: OBJECT_VERSIONS_SORT_BY,
  });

  const placeholder = useMemo(() => {
    if (loading) {
      return 'Loading monitors...';
    }
    if (monitorsResult.result?.length === 0) {
      return 'No monitors found';
    }
    if (monitorsResult.error) {
      return 'Error loading monitors';
    }
    return 'Select a monitor';
  }, [loading, monitorsResult.result, monitorsResult.error]);

  useMemo(() => {
    if (monitorsResult.result) {
      setMonitors(
        monitorsResult.result.map(monitor => ({
          label: monitor.val['name'],
          value: `weave:///${entity}/${project}/object/${monitor.objectId}:*`,
        }))
      );
      setLoading(false);
    }
  }, [monitorsResult.result, entity, project]);

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
