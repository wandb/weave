import React from 'react';

import {UnderConstruction} from './common/UnderConstruction';

export const TablesPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  return (
    <UnderConstruction
      title="Tables"
      message={
        <>This page will contain a listing of the Tables in the project</>
      }
    />
  );
};
