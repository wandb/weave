export const RUNNABLE_FEEDBACK_TYPE_PREFIX = 'wandb.runnable';

export const callQueryFieldForScorerOutput = (runnableName: string) =>
  `feedback.[${RUNNABLE_FEEDBACK_TYPE_PREFIX}.${runnableName}].payload.output`;

export const callQueryFieldForScorerVersion = (runnableName: string) =>
  `feedback.[${RUNNABLE_FEEDBACK_TYPE_PREFIX}.${runnableName}].runnable_ref`;
