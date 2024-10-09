export type VersionSpec = string | 'latest' | 'all';
export type Direction = 'asc' | 'desc';

export type LeaderboardConfigType = {
  version: number;
  config: {
    columns: Array<{
      dataset: {
        name: string;
        version: VersionSpec;
      };
      scores: Array<{
        scorer: {
          name: string;
          version: VersionSpec;
        };
        metrics: Array<{
          displayName: string;
          path: string[];
          minTrials?: number;
          maxTrials?: number;
          sort?: {
            precedence: number;
            direction: Direction;
          };
        }>;
      }>;
    }>;
    models: Array<{
      name: string;
      version: VersionSpec;
    }>;
  };
};
