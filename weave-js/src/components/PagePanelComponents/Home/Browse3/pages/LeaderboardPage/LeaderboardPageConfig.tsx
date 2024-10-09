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
    return [];
  }, []);
};

const useDatasetVersionsForDatasetName = (datasetName: string): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return [];
  }, []);
};

const useScorerNamesForDataset = (
  datasetName: string,
  datasetVersion: string
): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return [];
  }, []);
};

const useScorerVersionsForDatasetAndScorer = (
  datasetName: string,
  datasetVersion: string,
  scorerName: string
): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return [];
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
    return [];
  }, []);
};

const useModelNames = (): string[] => {
  // TODO: Implement this
  return useMemo(() => {
    return [];
  }, []);
};
