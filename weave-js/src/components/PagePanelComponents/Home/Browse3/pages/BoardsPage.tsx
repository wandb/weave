import React from 'react';

import {UnderConstruction} from './common/UnderConstruction';

export const BoardsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  return (
    <UnderConstruction
      title="Boards"
      message={
        <>This page will contain a listing of the boards in the project</>
      }
    />
  );
};
