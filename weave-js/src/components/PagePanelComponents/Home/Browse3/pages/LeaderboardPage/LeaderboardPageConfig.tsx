import {Box} from '@mui/material';
import React, {useMemo} from 'react';

type VersionSpec = string | 'latest' | 'all';
type Direction = 'asc' | 'desc';

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

export const LeaderboardConfig: React.FC<{
  currentConfig: LeaderboardConfigType;
  onConfigUpdate: (newConfig: LeaderboardConfigType) => void;
}> = props => {
  return (
    <Box
      sx={{
        width: '100%',
      }}>
      LeaderboardConfig
    </Box>
  );
};

export const useCurrentLeaderboardConfig = (): LeaderboardConfigType => {
  // TODO: Implement this
  return useMemo(() => {
    return {
      version: 1,
      config: {
        columns: [],
        models: [],
      },
    };
  }, []);
};

const useDatasetNames = (): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return [
      'leaderboard-test-dataset',
      'leaderboard-test-dataset-2',
      'leaderboard-test-dataset-3',
    ];
  }, []);
};

const useDatasetVersionsForDatasetName = (datasetName: string): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['dug657ioy8j1', 'dnkjubyhvasd', 'dadsgf3f451d'];
  }, []);
};

const useScorerNamesForDataset = (
  datasetName: string,
  datasetVersion: string
): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['scorer-1', 'scorer-2', 'scorer-3'];
  }, []);
};

const useScorerVersionsForDatasetAndScorer = (
  datasetName: string,
  datasetVersion: string,
  scorerName: string
): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['sug657ioy8j1', 'snkjubyhvasd', 'sadsgf3f451d'];
  }, []);
};

const useMetricPathsForDatasetAndScorer = (
  datasetName: string,
  datasetVersion: string,
  scorerName: string,
  scorerVersion: string
): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['accuracy', 'f1.macro', 'precision.micro', 'recall.micro.data'];
  }, []);
};

const useModelNames = (): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['model-1', 'model-2', 'model-3'];
  }, []);
};

const useModelVersionsForModelName = (modelName: string): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return ['mug657ioy8j1', 'mnkjubyhvasd', 'madsgf3f451d'];
  }, []);
};
