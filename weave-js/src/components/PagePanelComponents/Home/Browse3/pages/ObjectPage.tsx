import React from 'react';

import {SimplePageLayout} from './common/SimplePageLayout';
import {FilterableObjectVersionsTable} from './ObjectVersionsPage';

export const ObjectPage: React.FC<{
  entity: string;
  project: string;
  objectName: string;
}> = props => {
  return (
    <SimplePageLayout
      title={`Object: ${props.objectName}`}
      tabs={[
        {
          label: 'All Versions',
          content: (
            <FilterableObjectVersionsTable
              entity={props.entity}
              project={props.project}
              frozenFilter={{
                objectName: props.objectName,
              }}
            />
          ),
        },
      ]}
    />
  );
};
