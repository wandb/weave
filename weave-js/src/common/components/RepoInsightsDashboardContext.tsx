import React from 'react';

export interface RepoInsightsDashboardState {
  startDate: Date;
  endDate: Date;
  pageSize: number;
  repoName: string;

  frame: any;
}

export const RepoInsightsDashboardContext =
  React.createContext<RepoInsightsDashboardState>({
    startDate: new Date(),
    endDate: new Date(),
    pageSize: 0,
    repoName: '',
    frame: {},
  });
