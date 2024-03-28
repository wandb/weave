import React from 'react';

import {SimplePageLayout} from './common/SimplePageLayout';
import {FilterableTypeVersionsTable} from './TypeVersionsPage';

export const TypePage: React.FC<{
  entity: string;
  project: string;
  typeName: string;
}> = props => {
  return (
    <SimplePageLayout
      title={`Type: ${props.typeName}`}
      tabs={[
        {
          label: 'All Versions',
          content: (
            <FilterableTypeVersionsTable
              entity={props.entity}
              project={props.project}
              frozenFilter={{
                typeName: props.typeName,
              }}
            />
          ),
        },
      ]}
    />
  );
};
