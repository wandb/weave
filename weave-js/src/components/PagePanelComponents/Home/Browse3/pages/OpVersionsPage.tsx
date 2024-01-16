import {ListItemText} from '@material-ui/core';
import {
  Autocomplete,
  Checkbox,
  FormControl,
  ListItem,
  ListItemButton,
  TextField,
} from '@mui/material';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {Timestamp} from '../../../../Timestamp';
import {useWeaveflowRouteContext} from '../context';
import {CallsLink, OpVersionLink, OpVersionsLink} from './common/Links';
import {OpVersionCategoryChip} from './common/OpVersionCategoryChip';
import {
  FilterableTable,
  WFHighLevelDataColumn,
} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './wfInterface/context';
import {HackyOpCategory, WFOpVersion} from './wfInterface/types';

export type WFHighLevelOpVersionFilter = {
  opCategory?: HackyOpCategory | null;
  isLatest?: boolean;
  opName?: string | null;
  invokedByOpVersions?: string[];
  invokesOpVersions?: string[];
  consumesTypeVersions?: string[];
  producesTypeVersions?: string[];
};

export const OpVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelOpVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelOpVersionFilter) => void;
}> = props => {
  return (
    <SimplePageLayout
      // title="Op Versions"
      title="Operations"
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
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelOpVersionFilter) => void;
}> = props => {
  const {baseRouter} = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext(props.entity, props.project);

  const getInitialData = useCallback(
    (innerFilter: WFHighLevelOpVersionFilter) => {
      return orm.projectConnection.opVersions().map(o => {
        return {id: o.version(), obj: o};
      });
    },
    [orm.projectConnection]
  );

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

  // Initialize the filter
  const [filterState, setFilterState] = useState(props.initialFilter ?? {});
  // Update the filter when the initial filter changes
  useEffect(() => {
    if (props.initialFilter) {
      setFilterState(props.initialFilter);
    }
  }, [props.initialFilter]);

  // If the caller is controlling the filter, use the caller's filter state
  const filter = useMemo(
    () => (props.onFilterUpdate ? props.initialFilter ?? {} : filterState),
    [filterState, props.initialFilter, props.onFilterUpdate]
  );
  const setFilter = useMemo(
    () => (props.onFilterUpdate ? props.onFilterUpdate : setFilterState),
    [props.onFilterUpdate]
  );

  const columns = useMemo(() => {
    return {
      version: {
        columnId: 'version',
        gridDisplay: {
          columnLabel: 'Op',
          columnValue: obj => obj.obj.version(),
          gridColDefOptions: {
            renderCell: params => {
              return (
                <OpVersionLink
                  entityName={params.row.obj.entity()}
                  projectName={params.row.obj.project()}
                  opName={params.row.obj.op().name()}
                  version={params.row.obj.version()}
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
                    opVersions: [
                      params.row.obj.op().name() +
                        ':' +
                        params.row.obj.version(),
                    ],
                  }}
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
              return <OpVersionCategoryChip opCategory={params.value as any} />;
            },
            width: 100,
            minWidth: 100,
            maxWidth: 100,
          },
        },
        filterControls: {
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
        gridDisplay: !filter.isLatest
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
                    />
                  );
                },
                width: 100,
                minWidth: 100,
                maxWidth: 100,
              },
            },
        // gridDisplay: {
        //   columnLabel: 'Op',
        //   columnValue: obj => obj.obj.op().name(),
        //   gridColDefOptions: {
        //     renderCell: params => {
        //       return (
        //         <OpLink
        //           entityName={params.row.obj.entity()}
        //           projectName={params.row.obj.project()}
        //           opName={params.value as any}
        //         />
        //       );
        //     },
        //   },
        // },
        filterControls: {
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
      invokedByOpVersions: {
        columnId: 'invokedByOpVersions',
        // gridDisplay: {
        //   columnLabel: 'Invoked By',
        //   columnValue: obj => obj.obj.invokedBy().length,
        //   gridColDefOptions: {
        //     renderCell: params => {
        //       if (params.value === 0) {
        //         return '';
        //       }
        //       return (
        //         <OpVersionsLink
        //           entity={params.row.obj.entity()}
        //           project={params.row.obj.project()}
        //           versionCount={params.value as number}
        //           filter={{
        //             invokesOpVersions: [
        //               params.row.obj.op().name() +
        //                 ':' +
        //                 params.row.obj.version(),
        //             ],
        //           }}
        //         />
        //       );
        //     },
        //   },
        // },
        filterControls: {
          filterPredicate: ({obj}, innerFilter) => {
            if (
              innerFilter.invokedByOpVersions == null ||
              innerFilter.invokedByOpVersions.length === 0
            ) {
              return true;
            }
            return obj.invokedBy().some(version => {
              return innerFilter.invokedByOpVersions?.includes(
                version.op().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <InvokedByFilterControlListItem
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
        string[],
        number,
        'invokedByOpVersions',
        WFHighLevelOpVersionFilter
      >,
      invokesOpVersions: {
        columnId: 'invokesOpVersions',
        // gridDisplay: {
        //   columnLabel: 'Invokes',
        //   columnValue: obj => obj.obj.invokes().length,
        //   gridColDefOptions: {
        //     renderCell: params => {
        //       if (params.value === 0) {
        //         return '';
        //       }
        //       return (
        //         <OpVersionsLink
        //           entity={params.row.obj.entity()}
        //           project={params.row.obj.project()}
        //           versionCount={params.value as number}
        //           filter={{
        //             invokedByOpVersions: [
        //               params.row.obj.op().name() +
        //                 ':' +
        //                 params.row.obj.version(),
        //             ],
        //           }}
        //         />
        //       );
        //     },
        //   },
        // },
        filterControls: {
          filterPredicate: ({obj}, innerFilter) => {
            if (
              innerFilter.invokesOpVersions == null ||
              innerFilter.invokesOpVersions.length === 0
            ) {
              return true;
            }
            return obj.invokes().some(version => {
              return innerFilter.invokesOpVersions?.includes(
                version.op().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <InvokesFilterControlListItem
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
        string[],
        number,
        'invokesOpVersions',
        WFHighLevelOpVersionFilter
      >,
      consumesTypeVersions: {
        columnId: 'consumesTypeVersions',
        // gridDisplay: {
        //   columnLabel: 'Consumes Types',
        //   columnValue: obj => obj.obj.inputTypesVersions().length,
        //   gridColDefOptions: {
        //     renderCell: params => {
        //       if (params.value === 0) {
        //         return '';
        //       }
        //       return (
        //         <TypeVersionsLink
        //           entity={params.row.obj.entity()}
        //           project={params.row.obj.project()}
        //           versionCount={params.value as number}
        //           filter={{
        //             inputTo: [
        //               params.row.obj.op().name() +
        //                 ':' +
        //                 params.row.obj.version(),
        //             ],
        //           }}
        //         />
        //       );
        //     },
        //   },
        // },
        filterControls: {
          filterPredicate: ({obj}, innerFilter) => {
            if (
              innerFilter.consumesTypeVersions == null ||
              innerFilter.consumesTypeVersions.length === 0
            ) {
              return true;
            }
            return obj.inputTypesVersions().some(version => {
              return innerFilter.consumesTypeVersions?.includes(
                version.type().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <ConsumesTypeVersionFilterControlListItem
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
        string[],
        number,
        'consumesTypeVersions',
        WFHighLevelOpVersionFilter
      >,
      producesTypeVersions: {
        columnId: 'producesTypeVersions',
        // gridDisplay: {
        //   columnLabel: 'Produces Types',
        //   columnValue: obj => obj.obj.outputTypeVersions().length,
        //   gridColDefOptions: {
        //     renderCell: params => {
        //       if (params.value === 0) {
        //         return '';
        //       }
        //       return (
        //         <TypeVersionsLink
        //           entity={params.row.obj.entity()}
        //           project={params.row.obj.project()}
        //           versionCount={params.value as number}
        //           filter={{
        //             outputFrom: [
        //               params.row.obj.op().name() +
        //                 ':' +
        //                 params.row.obj.version(),
        //             ],
        //           }}
        //         />
        //       );
        //     },
        //   },
        // },
        filterControls: {
          filterPredicate: ({obj}, innerFilter) => {
            if (
              innerFilter.producesTypeVersions == null ||
              innerFilter.producesTypeVersions.length === 0
            ) {
              return true;
            }
            return obj.outputTypeVersions().some(version => {
              return innerFilter.producesTypeVersions?.includes(
                version.type().name() + ':' + version.version()
              );
            });
          },
          filterControlListItem: cellProps => {
            return (
              <ProducesTypeVersionFilterControlListItem
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
        string[],
        number,
        'producesTypeVersions',
        WFHighLevelOpVersionFilter
      >,
      // TODO: re-enable with editing support
      // description: {
      //   columnId: 'description',
      //   gridDisplay: {
      //     columnLabel: 'Description',
      //     columnValue: obj => obj.obj.description(),
      //     gridColDefOptions: {},
      //   },
      // } as WFHighLevelDataColumn<
      //   {obj: WFOpVersion},
      //   any,
      //   string,
      //   'description',
      //   WFHighLevelOpVersionFilter
      // >,
      versionIndex: {
        columnId: 'versionIndex',
        // gridDisplay: {
        //   columnLabel: 'Version Index',
        //   columnValue: obj => obj.obj.versionIndex(),
        //   gridColDefOptions: {},
        // },
      } as WFHighLevelDataColumn<
        {obj: WFOpVersion},
        any,
        number,
        'versionIndex',
        WFHighLevelOpVersionFilter
      >,
      isLatest: {
        columnId: 'isLatest',
        // gridDisplay: {
        //   columnLabel: 'Latest',
        //   columnValue: obj => obj.obj.aliases().includes('latest'),
        //   gridColDefOptions: {
        //     renderCell: params => {
        //       if (params.value) {
        //         return (
        //           <Box
        //             sx={{
        //               display: 'flex',
        //               alignItems: 'center',
        //               justifyContent: 'center',
        //               height: '100%',
        //               width: '100%',
        //             }}>
        //             <Chip label="Yes" size="small" />
        //           </Box>
        //         );
        //       }
        //       return '';
        //     },
        //   },
        // },
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
                    checked={!!colProps.filter?.isLatest}
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
  }, [filter.isLatest, props.entity, props.frozenFilter, props.project]);

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
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
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
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const options = useMemo(() => {
    return orm.projectConnection.ops().map(o => o.name());
  }, [orm.projectConnection]);
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
          options={options}
        />
      </FormControl>
    </ListItem>
  );
};

const InvokedByFilterControlListItem: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const optionsDict = useMemo(() => {
    return _.fromPairs(
      orm.projectConnection
        .opVersions()
        .filter(o => o.invokedBy().length > 0)
        .map(o => {
          return [
            o.op().name() + ':' + o.version(),
            o.op().name() + ':v' + o.versionIndex(),
          ];
        })
    );
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          limitTags={1}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'invokedByOpVersions'
          )}
          renderInput={params => <TextField {...params} label="Calls" />}
          value={props.filter.invokedByOpVersions ?? []}
          onChange={(event, newValue) => {
            props.updateFilter({
              invokedByOpVersions: newValue,
            });
          }}
          getOptionLabel={option => {
            return optionsDict[option];
          }}
          options={Object.keys(optionsDict)}
        />
      </FormControl>
    </ListItem>
  );
};

const InvokesFilterControlListItem: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const options = useMemo(() => {
    return orm.projectConnection
      .opVersions()
      .filter(o => o.invokes().length > 0)
      .map(o => {
        return o.op().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          limitTags={1}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'invokesOpVersions'
          )}
          renderInput={params => <TextField {...params} label="Called By" />}
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
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const options = useMemo(() => {
    return orm.projectConnection
      .typeVersions()
      .filter(o => o.inputTo().length > 0)
      .map(o => {
        return o.type().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);
  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          limitTags={1}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'consumesTypeVersions'
          )}
          renderInput={params => <TextField {...params} label="Parameters" />}
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
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelOpVersionFilter;
  filter: WFHighLevelOpVersionFilter;
  updateFilter: (update: Partial<WFHighLevelOpVersionFilter>) => void;
}> = props => {
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const options = useMemo(() => {
    return orm.projectConnection
      .typeVersions()
      .filter(o => o.outputFrom().length > 0)
      .map(o => {
        return o.type().name() + ':' + o.version();
      });
  }, [orm.projectConnection]);

  return (
    <ListItem>
      <FormControl fullWidth>
        <Autocomplete
          size={'small'}
          limitTags={1}
          multiple
          disabled={Object.keys(props.frozenFilter ?? {}).includes(
            'producesTypeVersions'
          )}
          renderInput={params => <TextField {...params} label="Returns" />}
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
