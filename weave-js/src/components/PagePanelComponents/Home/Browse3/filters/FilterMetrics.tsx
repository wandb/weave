import {Switch} from '@wandb/weave/components';
import React from 'react';

type FilterMetricsProps = {
  isMetricsChecked: boolean;
  setMetricsChecked: React.Dispatch<React.SetStateAction<boolean>>;
};

export const FilterMetrics = ({
  isMetricsChecked,
  setMetricsChecked,
}: FilterMetricsProps) => {
  return (
    <div className="flex items-center gap-6">
      <Switch.Root
        size="small"
        checked={isMetricsChecked}
        onCheckedChange={setMetricsChecked}>
        <Switch.Thumb size="small" checked={isMetricsChecked} />
      </Switch.Root>
      Metrics
    </div>
  );
};
