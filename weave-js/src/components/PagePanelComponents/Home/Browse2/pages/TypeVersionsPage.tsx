import {Autocomplete, FormControl, ListItem, TextField} from '@mui/material';
import React, {useCallback, useMemo} from 'react';

import {useWeaveflowRouteContext} from '../context';
import {
  ObjectVersionsLink,
  OpVersionsLink,
  TypeLink,
  TypeVersionLink,
  TypeVersionsLink,
} from './common/Links';
import {
  FilterableTable,
  WFHighLevelDataColumn,
} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {useWeaveflowORMContext} from './interface/wf/context';
import {HackyTypeCategory, WFTypeVersion} from './interface/wf/types';

export type WFHighLevelTypeVersionFilter = {
  typeName?: string | null;
  typeCategory?: HackyTypeCategory | null;
  inputTo?: string[];
  outputFrom?: string[];
  parentType?: string | null;
};

export const TypeVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelTypeVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelTypeVersionFilter) => void;
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
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelTypeVersionFilter) => void;
}> = props => {
  const routerContext = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext();

  const getInitialData = useCallback(
    (filter: WFHighLevelTypeVersionFilter) => {
      return orm.projectConnection.typeVersions().map(o => {
        return {id: o.version(), obj: o};
      });
    },
    [orm.projectConnection]
  );

  const getFilterPopoutTargetUrl = useCallback(
    (filter: WFHighLevelTypeVersionFilter) => {
      return routerContext.typeVersionsUIUrl(
        props.entity,
        props.project,
        filter
      );
    },
    [props.entity, props.project, routerContext]
  );

  const columns = useMemo(() => {
    return {
      version: {
        columnId: 'version',
        gridDisplay: {
          columnLabel: 'Version',
          columnValue: ({obj}) => {
            return obj.version();
          },
          gridColDefOptions: {
            renderCell: params => {
              return (
                <TypeVersionLink
                  typeName={params.row.obj.type().name()}
                  version={params.row.obj.version()}
                  hideName
                />
              );
            },
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFTypeVersion},
        string,
        string,
        'version',
        WFHighLevelTypeVersionFilter
      >,
      typeCategory: {
        columnId: 'typeCategory',
        gridDisplay: {
          columnLabel: 'Type Category',
          columnValue: ({obj}) => {
            return obj.typeCategory();
          },
          gridColDefOptions: {
            renderCell: params => {
              return (
                <TypeVersionCategoryChip
                  typeCategory={params.row.obj.typeCategory()}
                />
              );
            },
          },
        },
        filterControls: {
          filterPredicate: ({obj}, filter) => {
            if (filter.typeCategory == null) {
              return true;
            }
            return obj.typeCategory() === filter.typeCategory;
          },
          filterControlListItem: cellProps => {
            return (
              <TypeCategoryFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFTypeVersion},
        string,
        string,
        'typeCategory',
        WFHighLevelTypeVersionFilter
      >,
      typeName: {
        columnId: 'typeName',
        gridDisplay: {
          columnLabel: 'Type',
          columnValue: ({obj}) => {
            return obj.type().name();
          },
          gridColDefOptions: {
            renderCell: params => {
              return <TypeLink typeName={params.row.obj.type().name()} />;
            },
          },
        },
        filterControls: {
          filterPredicate: ({obj}, filter) => {
            if (filter.typeName == null) {
              return true;
            }
            return obj.type().name() === filter.typeName;
          },
          filterControlListItem: cellProps => {
            return (
              <TypeNameFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFTypeVersion},
        string,
        string,
        'typeName',
        WFHighLevelTypeVersionFilter
      >,

      objectVersions: {
        columnId: 'objectVersions',
        gridDisplay: {
          columnLabel: 'Object Versions',
          columnValue: ({obj}) => {
            return obj.objectVersions().length;
          },
          gridColDefOptions: {
            renderCell: params => {
              if (params.value == null || params.value === 0) {
                return null;
              }
              return (
                <ObjectVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  versionsCount={params.value}
                  filter={{
                    typeVersions: [
                      params.row.obj.type().name() +
                        ':' +
                        params.row.obj.version(),
                    ],
                  }}
                />
              );
            },
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFTypeVersion},
        any,
        number,
        'objectVersions',
        WFHighLevelTypeVersionFilter
      >,
      inputTo: {
        columnId: 'inputTo',
        gridDisplay: {
          columnLabel: 'Input To Op Versions',
          columnValue: ({obj}) => {
            return obj.inputTo().length;
          },
          gridColDefOptions: {
            renderCell: params => {
              if (params.value == null || params.value === 0) {
                return null;
              }
              return (
                <OpVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  versionCount={params.value}
                  filter={{
                    consumesTypeVersions: [
                      params.row.obj.type().name() +
                        ':' +
                        params.row.obj.version(),
                    ],
                  }}
                />
              );
            },
          },
        },
        filterControls: {
          filterPredicate: ({obj}, filter) => {
            if (filter.inputTo == null || filter.inputTo.length === 0) {
              return true;
            }
            return obj.inputTo().some(version => {
              return filter.inputTo?.includes(
                version.op().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <InputToFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFTypeVersion},
        string[],
        number,
        'inputTo',
        WFHighLevelTypeVersionFilter
      >,
      outputFrom: {
        columnId: 'outputFrom',
        gridDisplay: {
          columnLabel: 'Output From Op Versions',
          columnValue: ({obj}) => {
            return obj.outputFrom().length;
          },
          gridColDefOptions: {
            renderCell: params => {
              if (params.value == null || params.value === 0) {
                return null;
              }
              return (
                <OpVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  versionCount={params.value}
                  filter={{
                    producesTypeVersions: [
                      params.row.obj.type().name() +
                        ':' +
                        params.row.obj.version(),
                    ],
                  }}
                />
              );
            },
          },
        },
        filterControls: {
          filterPredicate: ({obj}, filter) => {
            if (filter.outputFrom == null || filter.outputFrom.length === 0) {
              return true;
            }
            return obj.outputFrom().some(version => {
              return filter.outputFrom?.includes(
                version.op().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <OutputFromFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFTypeVersion},
        string[],
        number,
        'outputFrom',
        WFHighLevelTypeVersionFilter
      >,
      parentType: {
        columnId: 'parentType',
        gridDisplay: {
          columnLabel: 'Super Type Version',
          columnValue: ({obj}) => {
            const parentTypeVersion = obj.parentTypeVersion();
            if (parentTypeVersion) {
              return (
                parentTypeVersion.type().name() +
                ':' +
                parentTypeVersion.version()
              );
            }
            return null;
          },
          gridColDefOptions: {
            renderCell: params => {
              if (params.value == null) {
                return null;
              }
              const parentTypeVersion = params.row.obj.parentTypeVersion();
              if (!parentTypeVersion) {
                return null;
              }
              return (
                <TypeVersionLink
                  typeName={parentTypeVersion.type().name()}
                  version={parentTypeVersion.version()}
                />
              );
            },
          },
        },
        filterControls: {
          filterPredicate: ({obj}, filter) => {
            if (filter.parentType == null || filter.parentType.length === 0) {
              return true;
            }
            const parentTypeVersion = obj.parentTypeVersion();
            if (!parentTypeVersion) {
              return false;
            }
            return (
              filter.parentType ===
              parentTypeVersion.type().name() +
                ':' +
                parentTypeVersion.version()
            );
          },
          filterControlListItem: cellProps => {
            return (
              <ParentTypeFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFTypeVersion},
        string,
        string | null,
        'parentType',
        WFHighLevelTypeVersionFilter
      >,
      childTypes: {
        columnId: 'childTypes',
        gridDisplay: {
          columnLabel: 'Sub Type Version',
          columnValue: ({obj}) => {
            return obj.childTypeVersions().length;
          },
          gridColDefOptions: {
            renderCell: params => {
              if (params.value == null || params.value === 0) {
                return null;
              }
              return (
                <TypeVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  versionCount={params.value}
                  filter={{
                    parentType:
                      params.row.obj.type().name() +
                      ':' +
                      params.row.obj.version(),
                  }}
                />
              );
            },
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFTypeVersion},
        any,
        number,
        'childTypes',
        WFHighLevelTypeVersionFilter
      >,
    };
  }, [props.frozenFilter]);

  return (
    <FilterableTable
      getInitialData={getInitialData}
      columns={columns}
      getFilterPopoutTargetUrl={getFilterPopoutTargetUrl}
      frozenFilter={props.frozenFilter}
      initialFilter={props.initialFilter}
      onFilterUpdate={props.onFilterUpdate}
    />
  );
};

const TypeCategoryFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelTypeVersionFilter;
  filter: WFHighLevelTypeVersionFilter;
  updateFilter: (update: Partial<WFHighLevelTypeVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection.typeCategories();
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'typeCategory'
          )}
          renderInput={params => (
            <TextField {...params} label="Type Category" />
          )}
          value={props.filter.typeCategory ?? null}
          onChange={(event, newValue) => {
            props.updateFilter({
              typeCategory: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const TypeNameFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelTypeVersionFilter;
  filter: WFHighLevelTypeVersionFilter;
  updateFilter: (update: Partial<WFHighLevelTypeVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection.types().map(o => o.name());
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          disabled={Object.keys(props.frozenFilter ?? {}).includes('type')}
          renderInput={params => <TextField {...params} label="Type Name" />}
          value={props.filter.typeName ?? null}
          onChange={(event, newValue) => {
            props.updateFilter({
              typeName: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const InputToFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelTypeVersionFilter;
  filter: WFHighLevelTypeVersionFilter;
  updateFilter: (update: Partial<WFHighLevelTypeVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection
      .opVersions()
      .filter(o => o.inputTypesVersions().length > 0)
      .map(o => {
        return o.op().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes('inputTo')}
          renderInput={params => <TextField {...params} label="Input To" />}
          value={props.filter.inputTo ?? []}
          onChange={(event, newValue) => {
            props.updateFilter({
              inputTo: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const OutputFromFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelTypeVersionFilter;
  filter: WFHighLevelTypeVersionFilter;
  updateFilter: (update: Partial<WFHighLevelTypeVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection
      .opVersions()
      .filter(o => o.outputTypeVersions().length > 0)
      .map(o => {
        return o.op().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'outputFrom'
          )}
          renderInput={params => <TextField {...params} label="Output From" />}
          value={props.filter.outputFrom ?? []}
          onChange={(event, newValue) => {
            props.updateFilter({
              outputFrom: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const ParentTypeFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelTypeVersionFilter;
  filter: WFHighLevelTypeVersionFilter;
  updateFilter: (update: Partial<WFHighLevelTypeVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection
      .typeVersions()
      .filter(o => o.childTypeVersions().length > 0)
      .map(o => {
        return o.type().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'parentType'
          )}
          renderInput={params => <TextField {...params} label="Parent Type" />}
          value={props.filter.parentType ?? null}
          onChange={(event, newValue) => {
            props.updateFilter({
              parentType: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};
