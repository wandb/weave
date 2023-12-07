import {Box, Chip, ListItemText} from '@material-ui/core';
import {
  Autocomplete,
  Checkbox,
  FormControl,
  ListItem,
  ListItemButton,
  TextField,
} from '@mui/material';
// import {NavigateNext} from '@mui/icons-material';
import moment from 'moment';
import React, {useCallback, useMemo} from 'react';

import {useWeaveflowRouteContext} from '../context';
import {
  CallsLink,
  OpLink,
  OpVersionLink,
  OpVersionsLink,
  TypeVersionsLink,
} from './common/Links';
import {OpVersionCategoryChip} from './common/OpVersionCategoryChip';
import {
  FilterableTable,
  WFHighLevelDataColumn,
} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {HackyOpCategory, WFOpVersion} from './interface/wf/types';

export type WFHighLevelOpVersionFilter = {
  opCategory?: HackyOpCategory | null; // TODO
  isLatest?: boolean; // TODO
  opName?: string | null; // TODO
  invokedByOpVersions?: string[]; // TODO
  invokesOpVersions?: string[]; // TODO
  consumesTypeVersions?: string[]; // TODO
  producesTypeVersions?: string[]; // TODO
};

export const OpVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelOpVersionFilter;
}> = props => {
  return (
    <SimplePageLayout
      title="Op Versions"
      tabs={[
        {
          label: 'All',
          content: <FilterableOpVersionsTable {...props} />,
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
}> = props => {
  const routerContext = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext();

  const getInitialData = useCallback(
    (filter: WFHighLevelOpVersionFilter) => {
      return orm.projectConnection.opVersions().map(o => {
        return {id: o.version(), obj: o};
      });
    },
    [orm.projectConnection]
  );

  const getFilterPopoutTargetUrl = useCallback(
    (filter: WFHighLevelOpVersionFilter) => {
      return routerContext.opVersionsUIUrl(props.entity, props.project, filter);
    },
    [props.entity, props.project, routerContext]
  );

  const columns = useMemo(() => {
    return {
      createdAt: {
        columnId: 'createdAt',
        gridDisplay: {
          columnLabel: 'Created At',
          columnValue: obj => obj.obj.createdAtMs(),
          gridColDefOptions: {
            renderCell: params => {
              return moment(params.value as number).format(
                'YYYY-MM-DD HH:mm:ss'
              );
            },
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        any,
        number,
        'createdAt',
        WFHighLevelOpVersionFilter
      >,
      version: {
        columnId: 'version',
        gridDisplay: {
          columnLabel: 'Version',
          columnValue: obj => obj.obj.version(),
          gridColDefOptions: {
            renderCell: params => {
              return (
                <OpVersionLink
                  opName={params.row.obj.op().name()}
                  version={params.row.obj.version()}
                  hideName
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
      opCategory: {
        columnId: 'opCategory',
        gridDisplay: {
          columnLabel: 'Op Category',
          columnValue: obj => obj.obj.opCategory(),
          gridColDefOptions: {
            renderCell: params => {
              return <OpVersionCategoryChip opCategory={params.value as any} />;
            },
          },
        },
        filterControls: {
          filterPredicate: ({obj}, filter) => {
            if (filter.opCategory == null) {
              return true;
            }
            return obj.opCategory() === filter.opCategory;
          },
          filterControlListItem: cellProps => {
            return (
              <OpCategoryFilterControlListItem
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
      opName: {
        columnId: 'opName',
        gridDisplay: {
          columnLabel: 'Op',
          columnValue: obj => obj.obj.op().name(),
          gridColDefOptions: {
            renderCell: params => {
              return <OpLink opName={params.value as any} />;
            },
          },
        },
        filterControls: {
          filterPredicate: ({obj}, filter) => {
            if (filter.opName == null) {
              return true;
            }
            return obj.op().name() === filter.opName;
          },
          filterControlListItem: cellProps => {
            return (
              <OpNameFilterControlListItem
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
      calls: {
        columnId: 'calls',
        gridDisplay: {
          columnLabel: 'Version',
          columnValue: obj => obj.obj.calls().length,
          gridColDefOptions: {
            renderCell: params => {
              if (params.value === 0) {
                return '';
              }
              return (
                <CallsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  callCount={params.value as number}
                  filter={{
                    opVersions: [
                      params.row.obj.op().name() +
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
        {obj: WFOpVersion},
        string[],
        number,
        'calls',
        WFHighLevelOpVersionFilter
      >,
      invokedByOpVersions: {
        columnId: 'invokedByOpVersions',
        gridDisplay: {
          columnLabel: 'Invoked By',
          columnValue: obj => obj.obj.invokedBy().length,
          gridColDefOptions: {
            renderCell: params => {
              if (params.value === 0) {
                return '';
              }
              return (
                <OpVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  versionCount={params.value as number}
                  filter={{
                    invokesOpVersions: [
                      params.row.obj.op().name() +
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
            if (
              filter.invokedByOpVersions == null ||
              filter.invokedByOpVersions.length === 0
            ) {
              return true;
            }
            return obj.invokedBy().some(version => {
              return filter.invokedByOpVersions?.includes(
                version.op().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <InvokedByFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        string[],
        number,
        'invokedByOpVersions',
        WFHighLevelOpVersionFilter
      >,
      invokesOpVersions: {
        columnId: 'invokesOpVersions',
        gridDisplay: {
          columnLabel: 'Invokes',
          columnValue: obj => obj.obj.invokes().length,
          gridColDefOptions: {
            renderCell: params => {
              if (params.value === 0) {
                return '';
              }
              return (
                <OpVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  versionCount={params.value as number}
                  filter={{
                    invokedByOpVersions: [
                      params.row.obj.op().name() +
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
            if (
              filter.invokesOpVersions == null ||
              filter.invokesOpVersions.length === 0
            ) {
              return true;
            }
            return obj.invokes().some(version => {
              return filter.invokesOpVersions?.includes(
                version.op().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <InvokesFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        string[],
        number,
        'invokesOpVersions',
        WFHighLevelOpVersionFilter
      >,
      consumesTypeVersions: {
        columnId: 'consumesTypeVersions',
        gridDisplay: {
          columnLabel: 'Consumes Types',
          columnValue: obj => obj.obj.inputTypesVersions().length,
          gridColDefOptions: {
            renderCell: params => {
              if (params.value === 0) {
                return '';
              }
              return (
                <TypeVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  versionCount={params.value as number}
                  filter={{
                    inputTo: [
                      params.row.obj.op().name() +
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
            if (
              filter.consumesTypeVersions == null ||
              filter.consumesTypeVersions.length === 0
            ) {
              return true;
            }
            return obj.inputTypesVersions().some(version => {
              return filter.consumesTypeVersions?.includes(
                version.type().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <ConsumesTypeVersionFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        string[],
        number,
        'consumesTypeVersions',
        WFHighLevelOpVersionFilter
      >,
      producesTypeVersions: {
        columnId: 'producesTypeVersions',
        gridDisplay: {
          columnLabel: 'Produces Types',
          columnValue: obj => obj.obj.outputTypeVersions().length,
          gridColDefOptions: {
            renderCell: params => {
              if (params.value === 0) {
                return '';
              }
              return (
                <TypeVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  versionCount={params.value as number}
                  filter={{
                    outputFrom: [
                      params.row.obj.op().name() +
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
            if (
              filter.producesTypeVersions == null ||
              filter.producesTypeVersions.length === 0
            ) {
              return true;
            }
            return obj.outputTypeVersions().some(version => {
              return filter.producesTypeVersions?.includes(
                version.type().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <ProducesTypeVersionFilterControlListItem
                frozenFilter={props.frozenFilter}
                {...cellProps}
              />
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        string[],
        number,
        'producesTypeVersions',
        WFHighLevelOpVersionFilter
      >,
      description: {
        columnId: 'description',
        gridDisplay: {
          columnLabel: 'Description',
          columnValue: obj => obj.obj.description(),
          gridColDefOptions: {},
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        any,
        string,
        'description',
        WFHighLevelOpVersionFilter
      >,
      versionIndex: {
        columnId: 'versionIndex',
        gridDisplay: {
          columnLabel: 'Version Index',
          columnValue: obj => obj.obj.versionIndex(),
          gridColDefOptions: {},
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        any,
        number,
        'versionIndex',
        WFHighLevelOpVersionFilter
      >,
      isLatest: {
        columnId: 'isLatest',
        gridDisplay: {
          columnLabel: 'Latest',
          columnValue: obj => obj.obj.aliases().includes('latest'),
          gridColDefOptions: {
            renderCell: params => {
              if (params.value) {
                return (
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      height: '100%',
                      width: '100%',
                    }}>
                    <Chip label="Yes" size="small" />
                  </Box>
                );
              }
              return '';
            },
          },
        },
        filterControls: {
          filterPredicate: ({obj}, {isLatest}) => {
            return !isLatest || obj.aliases().includes('latest') === isLatest;
          },
          filterControlListItem: colProps => {
            return (
              <ListItem
                secondaryAction={
                  <Checkbox
                    edge="end"
                    checked={colProps.filter?.isLatest}
                    onChange={() => {
                      colProps.updateFilter({
                        isLatest: !colProps.filter?.isLatest,
                      });
                    }}
                  />
                }
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'isLatest'
                )}
                disablePadding>
                <ListItemButton>
                  <ListItemText primary={`Latest Only`} />
                </ListItemButton>
              </ListItem>
            );
          },
        },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        boolean,
        boolean,
        'isLatest',
        WFHighLevelOpVersionFilter
      >, // filter me
    };
  }, [props.frozenFilter]);

  return (
    <FilterableTable
      getInitialData={getInitialData}
      columns={columns}
      getFilterPopoutTargetUrl={getFilterPopoutTargetUrl}
      frozenFilter={props.frozenFilter}
      initialFilter={props.initialFilter}
    />
  );
};

const OpCategoryFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection.opCategories();
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'opCategory'
          )}
          renderInput={params => <TextField {...params} label="Op Category" />}
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
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection.ops().map(o => o.name());
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          disabled={Object.keys(props.frozenFilter ?? {}).includes('opName')}
          renderInput={params => <TextField {...params} label="Op Name" />}
          value={props.filter.opName ?? null}
          onChange={(event, newValue) => {
            props.updateFilter({
              opName: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const InvokedByFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection
      .opVersions()
      .filter(o => o.invokedBy().length > 0)
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
            'invokedByOpVersions'
          )}
          renderInput={params => <TextField {...params} label="Invoked By" />}
          value={props.filter.invokedByOpVersions ?? []}
          onChange={(event, newValue) => {
            props.updateFilter({
              invokedByOpVersions: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const InvokesFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection
      .opVersions()
      .filter(o => o.invokes().length > 0)
      .map(o => {
        return o.op().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);
  console.log(props.filter);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'invokesOpVersions'
          )}
          renderInput={params => <TextField {...params} label="Invokes" />}
          value={props.filter.invokesOpVersions ?? []}
          onChange={(event, newValue) => {
            props.updateFilter({
              invokesOpVersions: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const ConsumesTypeVersionFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection
      .typeVersions()
      .filter(o => o.inputTo().length > 0)
      .map(o => {
        return o.type().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);
  console.log(props.filter);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'consumesTypeVersions'
          )}
          renderInput={params => (
            <TextField {...params} label="Consumes Type Versions" />
          )}
          value={props.filter.consumesTypeVersions ?? []}
          onChange={(event, newValue) => {
            props.updateFilter({
              consumesTypeVersions: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const ProducesTypeVersionFilterControlListItem: React.FC<{
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext();
  const options = useMemo(() => {
    return orm.projectConnection
      .typeVersions()
      .filter(o => o.outputFrom().length > 0)
      .map(o => {
        return o.type().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);
  console.log(props.filter);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'producesTypeVersions'
          )}
          renderInput={params => (
            <TextField {...params} label="Produces Type Versions" />
          )}
          value={props.filter.producesTypeVersions ?? []}
          onChange={(event, newValue) => {
            props.updateFilter({
              producesTypeVersions: newValue,
            });
          }}
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};
