import {DataGridPro, GridColDef, GridRowsProp} from '@mui/x-data-grid-pro';
import React, {useMemo} from 'react';

import {basicField} from './common/DataTable';
import {ObjectVersionsLink, TypeLink, TypeVersionLink} from './common/Links';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {WFTypeVersion} from './interface/wf/types';

export const TypeVersionsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const orm = useWeaveflowORMContext();

  const allTypeVersions = useMemo(() => {
    return orm.projectConnection.typeVersions();
  }, [orm.projectConnection]);
  return (
    <SimplePageLayout
      title="Type Versions"
      tabs={[
        {
          label: 'All',
          content: <TypeVersionsTable typeVersions={allTypeVersions} />,
        },
      ]}
    />
  );
};

export const TypeVersionsTable: React.FC<{
  typeVersions: WFTypeVersion[];
}> = props => {
  const rows: GridRowsProp = useMemo(() => {
    return props.typeVersions.map((tv, i) => {
      return {
        id: tv.version(),
        obj: tv,
        type: tv.type().name(),
        version: tv.version(),
        parentType: tv.parentTypeVersion(),
        childTypes: tv.childTypeVersions(),
        // inputTo: tv.inputTo(),
        // outputFrom: tv.outputFrom(),
        objectVersions: tv.objectVersions().length,
      };
    });
  }, [props.typeVersions]);
  const columns: GridColDef[] = [
    basicField('version', 'Version', {
      renderCell: params => {
        return (
          <TypeVersionLink
            typeName={params.row.type}
            version={params.row.version}
            hideName
          />
        );
      },
    }),
    basicField('type', 'Type', {
      renderCell: params => {
        return <TypeLink typeName={params.row.type} />;
      },
    }),
    // Keeping it simple for now
    // basicField('parentType', 'Parent Type'),
    // basicField('childTypes', 'Child Types'),
    // basicField('inputTo', 'Input To'),
    // basicField('outputFrom', 'Output From'),
    basicField('objectVersions', 'Object Versions', {
      renderCell: params => {
        if (params.value === 0) {
          return null;
        }
        return (
          <ObjectVersionsLink
            entity={params.row.obj.entity()}
            project={params.row.obj.project()}
            versionsCount={params.value}
            filter={{
              typeVersions: [params.row.type + ':' + params.row.version],
            }}
          />
        );
      },
    }),
  ];
  return (
    <DataGridPro
      rows={rows}
      rowHeight={38}
      columns={columns}
      experimentalFeatures={{columnGrouping: true}}
      disableRowSelectionOnClick
    />
  );
};
