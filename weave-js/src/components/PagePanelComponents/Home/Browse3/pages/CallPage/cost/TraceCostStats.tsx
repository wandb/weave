import Box from '@mui/material/Box';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Pill} from '@wandb/weave/components/Tag';
import {formatNumber} from '@wandb/weave/core/util/number';
import React, {ReactNode} from 'react';

import {IconName} from '../../../../../../Icon';
import {Tooltip} from '../../../../../../Tooltip';
import {
  LLMCostSchema,
  LLMUsageSchema,
} from '../../wfReactInterface/traceServerClientTypes';
import {getCostFromCostData, getTokensFromUsage} from './costUtils';

export const TraceStat = ({
  icon,
  label,
  tooltip,
}: {
  icon?: IconName;
  label: string;
  tooltip?: ReactNode;
}) => {
  const trigger = (
    <div>
      <Pill
        icon={icon}
        label={label}
        color="moon"
        className="bg-transparent text-moon-500 dark:bg-transparent dark:text-moon-500"
      />
    </div>
  );

  if (!tooltip) {
    return trigger;
  }

  return <Tooltip trigger={trigger} content={tooltip} />;
};

export const TraceCostStats = ({
  usageData,
  costData,
  latency_ms,
  costLoading,
}: {
  usageData: {[key: string]: LLMUsageSchema} | undefined;
  costData: {[key: string]: LLMCostSchema} | undefined;
  latency_ms: number;
  costLoading: boolean;
}) => {
  const latencyS = latency_ms / 1000;
  const {cost, costToolTipContent} = getCostFromCostData(costData);
  const {tokens, tokenToolTipContent} = getTokensFromUsage(usageData);

  const latency =
    (latencyS < 0.01 ? '<0.01' : formatNumber(latencyS, 'Number')) + 's';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
      }}>
      <TraceStat icon="recent-clock" label={latency} />
      {/* Tokens */}
      {usageData && tokens && (
        <>
          <TraceStat
            icon="database-artifacts"
            label={tokens.toString()}
            tooltip={tokenToolTipContent}
          />
          {/* Cost */}
          {costLoading ? (
            <LoadingDots />
          ) : costData && cost ? (
            <TraceStat label={cost} tooltip={costToolTipContent} />
          ) : (
            <></>
          )}
        </>
      )}
    </Box>
  );
};
