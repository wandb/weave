import {Autocomplete, FormControl, ListItem, TextField} from '@mui/material';
import _ from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {Timestamp} from '../../../../Timestamp';
import {useWeaveflowRouteContext} from '../context';
import {CategoryChip} from './common/CategoryChip';
import {
  CallsLink,
  opNiceName,
  OpVersionLink,
  OpVersionsLink,
} from './common/Links';
import {
  FilterableTable,
  WFHighLevelDataColumn,
} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useInitializingFilter} from './util';
import {useWeaveflowORMContext} from './wfInterface/context';
import {HackyOpCategory, WFOpVersion} from './wfInterface/types';

export type WFHighLevelOpVersionFilter = {
  opCategory?: HackyOpCategory | null;
  opName?: string | null;
};

export const OpVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelOpVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelOpVersionFilter) => void;
}> = props => {
  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const title = useMemo(() => {
    if (filter.opName) {
      return 'Implementations of ' + filter.opName;
    } else if (filter.opCategory) {
      return _.capitalize(filter.opCategory) + ' Operations';
    }
    return 'All Operations';
  }, [filter.opCategory, filter.opName]);

  return (
    <SimplePageLayout
      title={title}
      hideTabsIfSingle
      tabs={[
        {
          label: '',
          content: (
            <FilterableOpVersionsTable
              {...props}
              initialFilter={filter}
              onFilterUpdate={setFilter}
            />
          ),
        },
      ]}
    />
  );
};

export const FilterableOpVersionsTable: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelOpVersionFilter;
  initialFilter?: WFHighLevelOpVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelOpVersionFilter) => void;
}> = props => {
  const {baseRouter} = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext(props.entity, props.project);

  const getInitialData = useCallback(() => {
    return orm.projectConnection.opVersions().map(o => {
      return {id: o.refUri(), obj: o};
    });
  }, [orm.projectConnection]);

  const getFilterPopoutTargetUrl = useCallback(
    (innerFilter: WFHighLevelOpVersionFilter) => {
      return baseRouter.opVersionsUIUrl(
        props.entity,
        props.project,
        innerFilter
      );
    },
    [props.entity, props.project, baseRouter]
  );

  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const showLatestOnly = !filter.opName;

  const columns = useMemo(() => {
    return {
      version: {
        columnId: 'version',
        gridDisplay: {
          columnLabel: 'Op',
          columnValue: obj => obj.obj.refUri(),
          gridColDefOptions: {
            hideable: false,
            renderCell: params => {
              return (
                <OpVersionLink
                  entityName={params.row.obj.entity()}
                  projectName={params.row.obj.project()}
                  opName={params.row.obj.op().name()}
                  version={params.row.obj.commitHash()}
                  versionIndex={params.row.obj.versionIndex()}
                />
              );
            },
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        any,
        string,
        'version',
        WFHighLevelOpVersionFilter
      >,

      calls: {
        columnId: 'calls',
        gridDisplay: {
          columnLabel: 'Calls',
          columnValue: obj => obj.obj.calls().length,
          gridColDefOptions: {
            renderCell: params => {
              if (params.value === 0) {
                return '';
              }
              return (
                <CallsLink
                  neverPeek
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  callCount={params.value as number}
                  filter={{
                    opVersionRefs: [params.row.obj.refUri()],
                  }}
                  variant="secondary"
                />
              );
            },
            width: 100,
            minWidth: 100,
            maxWidth: 100,
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        string[],
        number,
        'calls',
        WFHighLevelOpVersionFilter
      >,

      opCategory: {
        columnId: 'opCategory',
        gridDisplay: {
          columnLabel: 'Category',
          columnValue: obj => obj.obj.opCategory(),
          gridColDefOptions: {
            renderCell: params => {
              return params.value && <CategoryChip value={params.value} />;
            },
            width: 100,
            minWidth: 100,
            maxWidth: 100,
          },
        },
        filterControls: {
          filterKeys: ['opCategory'],
          filterPredicate: ({obj}, innerFilter) => {
            if (innerFilter.opCategory == null) {
              return true;
            }
            return obj.opCategory() === innerFilter.opCategory;
          },
          filterControlListItem: cellProps => {
            return (
              <OpCategoryFilterControlListItem
                entity={props.entity}
                project={props.project}
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        string,
        string,
        'opCategory',
        WFHighLevelOpVersionFilter
      >,

      createdAt: {
        columnId: 'createdAt',
        gridDisplay: {
          columnLabel: 'Created',
          columnValue: obj => obj.obj.createdAtMs(),
          gridColDefOptions: {
            renderCell: params => {
              return (
                <Timestamp
                  value={(params.value as number) / 1000}
                  format="relative"
                />
              );
            },
            width: 100,
            minWidth: 100,
            maxWidth: 100,
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        any,
        number,
        'createdAt',
        WFHighLevelOpVersionFilter
      >,

      opName: {
        columnId: 'opName',
        // This grid display does not match the data for the column
        // ... a bit of a hack
        gridDisplay: !showLatestOnly
          ? undefined
          : {
              columnLabel: 'Versions',
              columnValue: obj => obj.obj.op().name(),
              gridColDefOptions: {
                renderCell: params => {
                  return (
                    <OpVersionsLink
                      entity={params.row.obj.entity()}
                      project={params.row.obj.project()}
                      versionCount={params.row.obj.op().opVersions().length}
                      filter={{
                        opName: params.row.obj.op().name(),
                      }}
                      neverPeek
                      variant="secondary"
                    />
                  );
                },
                width: 100,
                minWidth: 100,
                maxWidth: 100,
              },
            },
        filterControls: {
          filterKeys: ['opName'],
          filterPredicate: ({obj}, innerFilter) => {
            if (innerFilter.opName == null) {
              return true;
            }
            return obj.op().name() === innerFilter.opName;
          },
          filterControlListItem: cellProps => {
            return (
              <OpNameFilterControlListItem
                entity={props.entity}
                project={props.project}
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        string,
        string,
        'opName',
        WFHighLevelOpVersionFilter
      >,
    };
  }, [props.entity, props.frozenFilter, props.project, showLatestOnly]);

  return (
    <FilterableTable
      getInitialData={getInitialData}
      columns={columns}
      getFilterPopoutTargetUrl={getFilterPopoutTargetUrl}
      frozenFilter={props.frozenFilter}
      initialFilter={filter}
      onFilterUpdate={setFilter}
    />
  );
};

const OpCategoryFilterControlListItem: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
  frozenData: Array<{obj: WFOpVersion}>;
}> = props => {
  const options = useMemo(() => {
    return _.uniq(props.frozenData.map(item => item.obj.opCategory()))
      .filter(item => item != null)
      .sort() as HackyOpCategory[];
  }, [props.frozenData]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'opCategory'
          )}
          renderInput={params => <TextField {...params} label="Category" />}
          value={props.filter.opCategory ?? null}
          onChange={(event, newValue) => {
            props.updateFilter({
              opCategory: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const OpNameFilterControlListItem: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
  frozenData: Array<{obj: WFOpVersion}>;
}> = props => {
  const options = useMemo(() => {
    return _.uniq(props.frozenData.map(item => item.obj.op().name())).sort(
      (a, b) => {
        const nameA = opNiceName(a);
        const nameB = opNiceName(b);
        return nameA.localeCompare(nameB);
      }
    );
  }, [props.frozenData]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          disabled={Object.keys(props.frozenFilter ?? {}).includes('opName')}
          renderInput={params => <TextField {...params} label="Name" />}
          value={props.filter.opName ?? null}
          onChange={(event, newValue) => {
            props.updateFilter({
              opName: newValue,
            });
          }}
          getOptionLabel={option => opNiceName(option)}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};
