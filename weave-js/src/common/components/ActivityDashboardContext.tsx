// ActivityDashboardContext is used to manage page state including filter selections
// Nominally, CG expressions receive their parameters through the frame,

import React from 'react';

// but we need to keep raw copies of filter selections for certain optimizations
export interface ActivityDashboardContextState {
  startDate: Date;
  endDate: Date;
  userFilter: string[];
  pageSize: number;

  frame: any;

  safeLoad: boolean;
}

export const ActivityDashboardContext =
  React.createContext<ActivityDashboardContextState>({
    startDate: new Date(),
    endDate: new Date(),
    userFilter: [],
    pageSize: 0,
    frame: {},
    safeLoad: false,
  });
