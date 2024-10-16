import React from 'react';

import {Id} from '../pages/common/Id';

type IdListProps = {
  ids: string[];
  type: string;
};

export const IdList = ({ids, type}: IdListProps) => {
  return (
    <div className="flex items-center">
      {ids.map((id: string) => (
        <Id key={id} id={id} type={type} />
      ))}
    </div>
  );
};
