import {Leaderboard} from '../../../pages/wfReactInterface/generatedBuiltinObjectClasses.zod';

export const ALL_VALUE = '*';

export type LeaderboardConfigType = {
  version: number;
  config: {
    description: string;
    dataSelectionSpec: FilterAndGroupSpec;
  };
};

export type FilterAndGroupSpec = {
  sourceEvaluations?: FilterAndGroupSourceEvaluationSpec[]; // null is all
  datasets?: FilterAndGroupDatasetSpec[]; // null is all
  models?: FilterAndGroupModelSpec[]; // null is all
};

export type FilterAndGroupSourceEvaluationSpec = {
  name: string;
  version: string; // "*" means all
};

export type FilterAndGroupDatasetSpec = {
  name: string; // "*" means all
  version: string; // "*" means all
  groupAllVersions?: boolean;
  scorers?: FilterAndGroupDatasetScorerSpec[]; // null is all
};

export type FilterAndGroupDatasetScorerSpec = {
  name: string; // "*" means all
  version: string; // "*" means all
  groupAllVersions?: boolean;
  metrics?: FilterAndGroupDatasetScorerMetricSpec[]; // null is all
};

export type FilterAndGroupDatasetScorerMetricSpec = {
  path: string; // "*" means all
  shouldMinimize?: boolean;
};

export type FilterAndGroupModelSpec = {
  name: string; // "*" means all
  version: string; // "*" means all
  groupAllVersions?: boolean;
};

// This alias could go away, just here to make refactoring easier
export type LeaderboardObjectVal = Leaderboard;
