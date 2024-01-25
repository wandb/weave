import React from 'react';

// import {SimplePageLayout} from './common/SimplePageLayout';

export const CompareCallsPage: React.FC<{
  entity: string;
  project: string;
  callIds?: string[];
  primaryDim?: string;
  secondaryDim?: string;
}> = props => {
  console.log(props);
  return <>{JSON.stringify(props)}</>;
};
