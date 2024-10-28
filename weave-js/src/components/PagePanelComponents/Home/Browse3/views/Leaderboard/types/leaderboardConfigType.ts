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

// TODO: Merge into weave-js/src/components/PagePanelComponents/Home/Browse3/collections/collectionRegistry.ts after
// Online evals lands
export type LeaderboardObjectVal = {
  name: string;
  description: string;
  columns: Array<{
    evaluation_object_ref: string;
    scorer_name: string;
    should_minimize?: boolean;
    summary_metric_path_parts: string[];
  }>;
};
