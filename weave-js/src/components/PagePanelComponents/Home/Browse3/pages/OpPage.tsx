import React from 'react';

import {SimplePageLayout} from './common/SimplePageLayout';
import {FilterableOpVersionsTable} from './OpVersionsPage';

export const OpPage: React.FC<{
  entity: string;
  project: string;
  opName: string;
}> = props => {
  return (
    <SimplePageLayout
      title={`Op: ${props.opName}`}
      tabs={[
        {
          label: 'All Versions',
          content: (
            <FilterableOpVersionsTable
              entity={props.entity}
              project={props.project}
              frozenFilter={{
                opName: props.opName,
              }}
            />
          ),
        },
      ]}
    />
  );
};
