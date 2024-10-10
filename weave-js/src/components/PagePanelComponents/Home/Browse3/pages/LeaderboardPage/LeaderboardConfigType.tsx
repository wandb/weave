export type VersionSpec = string | 'latest' | 'all';
export type Direction = 'asc' | 'desc';

export type LeaderboardConfigType = {
  version: number;
  config: {
    description: string;
    dataSelectionSpec: FilterAndGroupSpec;
  };
};

export type FilterAndGroupSpec = {
  datasets?: FilterAndGroupDatasetSpec[]; // null is all
  models?: FilterAndGroupModelSpec[]; // null is all
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
