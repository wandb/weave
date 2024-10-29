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
    <div className="flex gap-6">
      <Switch.Root
        size="medium"
        checked={isMetricsChecked}
        onCheckedChange={setMetricsChecked}>
        <Switch.Thumb size="medium" checked={isMetricsChecked} />
      </Switch.Root>
      Metrics
    </div>
  );
};
