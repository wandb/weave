import {DataGridPro, GridColDef, GridRowsProp} from '@mui/x-data-grid-pro';
import React, {useEffect, useMemo, useState} from 'react';

import {useWeaveflowRouteContext} from '../context';
import {basicField} from './common/DataTable';
import {ObjectVersionsLink, TypeLink, TypeVersionLink} from './common/Links';
import {FilterLayoutTemplate} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {WFTypeVersion} from './interface/wf/types';

export type WFHighLevelTypeVersionFilter = {};

export const TypeVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelTypeVersionFilter;
}> = props => {
  return (
    <SimplePageLayout
      title="Type Versions"
      tabs={[
        {
          label: 'All',
          content: <FilterableTypeVersionsTable {...props} />,
        },
      ]}
    />
  );
};

export const FilterableTypeVersionsTable: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelTypeVersionFilter;
  initialFilter?: WFHighLevelTypeVersionFilter;
}> = props => {
  const [filter, setFilter] = useState<WFHighLevelTypeVersionFilter>(
    props.initialFilter ?? {}
  );
  useEffect(() => {
    if (props.initialFilter) {
      setFilter(props.initialFilter);
    }
  }, [props.initialFilter]);
  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter};
  }, [filter, props.frozenFilter]);

  const routerContext = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext();
  const allTypeVersions = useMemo(() => {
    return orm.projectConnection.typeVersions();
  }, [orm.projectConnection]);
  const filteredTypeVersions = useMemo(() => {
    return allTypeVersions;
  }, [allTypeVersions]);

  return (
    <FilterLayoutTemplate
      filterPopoutTargetUrl={routerContext.typeVersionsUIUrl(
        props.entity,
        props.project,
        effectiveFilter
      )}
      filterListItems={<></>}>
      <TypeVersionsTable typeVersions={filteredTypeVersions} />
    </FilterLayoutTemplate>
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
