import {
  Autocomplete,
  Checkbox,
  FormControl,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
} from '@mui/material';
import {
  GridColDef,
  GridColumnGroupingModel,
  GridRowSelectionModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {Timestamp} from '../../../../Timestamp';
import {useWeaveflowRouteContext} from '../context';
import {StyledDataGrid} from '../StyledDataGrid';
import {basicField} from './common/DataTable';
import {ObjectVersionLink, ObjectVersionsLink} from './common/Links';
import {FilterLayoutTemplate} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {
  truncateID,
  useInitializingFilter,
  useURLSearchParamsDict,
} from './util';
import {useWeaveflowORMContext} from './wfInterface/context';
import {
  HackyTypeCategory,
  WFObjectVersion,
  WFOpVersion,
} from './wfInterface/types';

// TODO: This file follows the older pattern - need to update it to use the same
// one as TypeVersionsPage or OpVersionsPage

export const ObjectVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelObjectVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelObjectVersionFilter) => void;
}> = props => {
  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const title = useMemo(() => {
    if (filter.typeCategory) {
      return _.capitalize(filter.typeCategory) + ' Objects';
    }
    return 'Objects';
  }, [filter.typeCategory]);

  return (
    <SimplePageLayout
      // title="Object Versions"
      title={title}
      tabs={[
        {
          label: 'All',
          content: (
            <FilterableObjectVersionsTable
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

export type WFHighLevelObjectVersionFilter = {
  objectName?: string | null;
  typeVersions?: string[];
  latest?: boolean;
  typeCategory?: HackyTypeCategory | null;
  inputToOpVersions?: string[];
};

export const FilterableObjectVersionsTable: React.FC<{
  entity: string;
  project: string;
  frozenFilter?: WFHighLevelObjectVersionFilter;
  initialFilter?: WFHighLevelObjectVersionFilter;
  // Setting this will make the component a controlled component. The parent
  // is responsible for updating the filter.
  onFilterUpdate?: (filter: WFHighLevelObjectVersionFilter) => void;
}> = props => {
  const {baseRouter} = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext(props.entity, props.project);
  const allObjectVersions = useMemo(() => {
    return orm.projectConnection.objectVersions();
  }, [orm.projectConnection]);

  const {filter, setFilter} = useInitializingFilter(
    props.initialFilter,
    props.onFilterUpdate
  );

  const effectiveFilter = useMemo(() => {
    return {...filter, ...props.frozenFilter};
  }, [filter, props.frozenFilter]);

  const filteredObjectVersions = useMemo(() => {
    return applyFilter(allObjectVersions, effectiveFilter);
  }, [allObjectVersions, effectiveFilter]);

  // const objectOptions = useMemo(() => {
  //   const objects = orm.projectConnection.objects();
  //   const options = objects.map(v => v.name());
  //   return options;
  // }, [orm.projectConnection]);
  const objectOptions = useObjectOptions(allObjectVersions, effectiveFilter);

  // const typeCategoryOptions = useMemo(() => {
  //   return orm.projectConnection.typeCategories();
  // }, [orm.projectConnection]);
  const typeCategoryOptions = useTypeCategoryOptions(
    allObjectVersions,
    effectiveFilter
  );

  // const opVersionOptions = useMemo(() => {
  //   const versions = orm.projectConnection.opVersions();
  //   // Note: this excludes the named ones without op versions
  //   const options = versions.map(v => v.op().name() + ':' + v.version());
  //   return options;
  // }, [orm.projectConnection]);
  const opVersionOptions = useOpVersionOptions(
    allObjectVersions,
    effectiveFilter
  );

  const latestOnlyOptions = useLatestOnlyOptions(
    allObjectVersions,
    effectiveFilter
  );

  return (
    <FilterLayoutTemplate
      showFilterIndicator={Object.keys(effectiveFilter ?? {}).length > 0}
      showPopoutButton={Object.keys(props.frozenFilter ?? {}).length > 0}
      filterPopoutTargetUrl={baseRouter.objectVersionsUIUrl(
        props.entity,
        props.project,
        effectiveFilter
      )}
      filterListItems={
        <>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'typeCategory'
                )}
                renderInput={params => (
                  <TextField {...params} label="Category" />
                  // <TextField {...params} label="Type Category" />
                )}
                value={effectiveFilter.typeCategory ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    typeCategory: newValue,
                  });
                }}
                options={typeCategoryOptions}
              />
            </FormControl>
          </ListItem>

          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'objectName'
                )}
                renderInput={params => (
                  // <TextField {...params} label="Object Name" />
                  <TextField {...params} label="Name" />
                )}
                value={effectiveFilter.objectName ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    objectName: newValue,
                  });
                }}
                options={objectOptions}
              />
            </FormControl>
          </ListItem>

          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                limitTags={1}
                // Temp disable multiple for simplicity - may want to re-enable
                // multiple
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'inputToOpVersions'
                )}
                renderInput={params => (
                  <TextField {...params} label="Input To" />
                )}
                value={effectiveFilter.inputToOpVersions?.[0] ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    inputToOpVersions: newValue ? [newValue] : [],
                  });
                }}
                getOptionLabel={option => {
                  return opVersionOptions[option] ?? option;
                }}
                options={Object.keys(opVersionOptions)}
              />
            </FormControl>
          </ListItem>
          <ListItem
            secondaryAction={
              <Checkbox
                edge="end"
                checked={
                  !!effectiveFilter.latest ||
                  (latestOnlyOptions.length === 1 && latestOnlyOptions[0])
                }
                onChange={() => {
                  setFilter({
                    ...filter,
                    latest: !effectiveFilter.latest,
                  });
                }}
              />
            }
            disabled={
              Object.keys(props.frozenFilter ?? {}).includes('latest') ||
              latestOnlyOptions.length <= 1
            }
            disablePadding>
            <ListItemButton
              onClick={() => {
                setFilter({
                  ...filter,
                  latest: !effectiveFilter.latest,
                });
              }}>
              <ListItemText primary="Latest Only" />
            </ListItemButton>
          </ListItem>
        </>
      }>
      <ObjectVersionsTable
        objectVersions={filteredObjectVersions}
        usingLatestFilter={effectiveFilter.latest}
      />
    </FilterLayoutTemplate>
  );
};

const ObjectVersionsTable: React.FC<{
  objectVersions: WFObjectVersion[];
  usingLatestFilter?: boolean;
}> = props => {
  const rows: GridRowsProp = useMemo(() => {
    return props.objectVersions.map((ov, i) => {
      const outputFrom = ov.outputFrom();
      const firstOutputFromOpVersion =
        outputFrom.length > 0 ? outputFrom[0].opVersion() : null;
      const firstOutputFrom = firstOutputFromOpVersion
        ? firstOutputFromOpVersion.op().name() +
          ':' +
          firstOutputFromOpVersion.version()
        : null;
      return {
        id: ov.version(),
        obj: ov,
        object: ov.object().name(),
        typeCategory: ov.typeVersion().typeCategory(),
        version: ov.version(),
        typeVersion:
          ov.typeVersion().type().name() + ':' + ov.typeVersion().version(),
        inputTo: ov.inputTo().length,
        outputFrom: firstOutputFrom,
        // description: ov.description(),
        versionIndex: ov.versionIndex(),
        createdAt: ov.createdAtMs(),
        isLatest: ov.aliases().includes('latest'),
      };
    });
  }, [props.objectVersions]);
  const columns: GridColDef[] = [
    basicField('version', 'Object', {
      hideable: false,
      renderCell: params => {
        // Icon to indicate navigation to the object version
        return (
          <ObjectVersionLink
            entityName={params.row.obj.entity()}
            projectName={params.row.obj.project()}
            objectName={params.row.obj.object().name()}
            version={params.row.obj.version()}
            versionIndex={params.row.obj.versionIndex()}
          />
        );
      },
    }),
    basicField('typeCategory', 'Category', {
      width: 100,
      renderCell: cellParams => {
        return (
          <TypeVersionCategoryChip typeCategory={cellParams.row.typeCategory} />
        );
      },
    }),
    basicField('createdAt', 'Created', {
      width: 100,
      renderCell: params => {
        return (
          <Timestamp
            value={(params.value as number) / 1000}
            format="relative"
          />
        );
      },
    }),
    // basicField('object', 'Object', {
    //   renderCell: params => (
    //     <ObjectLink
    //       entityName={params.row.obj.entity()}
    //       projectName={params.row.obj.project()}
    //       objectName={params.value as string}
    //     />
    //   ),
    // }),

    // basicField('typeVersion', 'Type Version', {
    //   renderCell: params => (
    //     <TypeVersionLink
    //       entityName={params.row.obj.entity()}
    //       projectName={params.row.obj.project()}
    //       typeName={params.row.obj.typeVersion().type().name()}
    //       version={params.row.obj.typeVersion().version()}
    //     />
    //   ),
    // }),
    // basicField('inputTo', 'Input To', {
    //   width: 100,
    //   renderCell: params => {
    //     if (params.value === 0) {
    //       return '';
    //     }

    //     return (
    //       <CallsLink
    //         entity={params.row.obj.entity()}
    //         project={params.row.obj.project()}
    //         callCount={params.value}
    //         filter={{
    //           inputObjectVersions: [
    //             params.row.obj.object().name() + ':' + params.row.obj.version(),
    //           ],
    //         }}
    //       />
    //     );
    //   },
    // }),
    // basicField('outputFrom', 'Output From', {
    //   width: 100,
    //   renderCell: params => {
    //     if (!params.value) {
    //       return '';
    //     }
    //     const outputFrom = params.row.obj.outputFrom();
    //     if (outputFrom.length === 0) {
    //       return '';
    //     }
    //     // if (outputFrom.length === 1) {
    //     return (
    //       <OpVersionLink
    //         entityName={outputFrom[0].entity()}
    //         projectName={outputFrom[0].project()}
    //         opName={outputFrom[0].opVersion().op().name()}
    //         version={outputFrom[0].opVersion().version()}
    //         versionIndex={outputFrom[0].opVersion().versionIndex()}
    //       />
    //     );
    //   },
    // }),
    // basicField('versionIndex', 'Version', {
    //   width: 100,
    // }),

    ...(props.usingLatestFilter
      ? [
          basicField('peerVersions', 'Versions', {
            width: 100,
            renderCell: params => {
              return (
                <ObjectVersionsLink
                  entity={params.row.obj.entity()}
                  project={params.row.obj.project()}
                  filter={{
                    objectName: params.row.obj.object().name(),
                  }}
                  versionCount={params.row.obj.object().objectVersions().length}
                  neverPeek
                />
              );
            },
          }),
        ]
      : []),
    // : [basicField('isLatest', 'Latest', {
    //     width: 100,
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
    //   }),]
  ];
  const columnGroupingModel: GridColumnGroupingModel = [];

  // Highlight table row if it matches peek drawer.
  const query = useURLSearchParamsDict();
  const {peekPath} = query;
  const peekId = peekPath ? peekPath.split('/').pop() : null;
  const rowIds = useMemo(() => {
    return rows.map(row => row.id);
  }, [rows]);
  const [rowSelectionModel, setRowSelectionModel] =
    useState<GridRowSelectionModel>([]);
  useEffect(() => {
    if (rowIds.length === 0) {
      // Data may have not loaded
      return;
    }
    if (peekId == null) {
      // No peek drawer, clear any selection
      setRowSelectionModel([]);
    } else {
      // If peek drawer matches a row, select it.
      // If not, don't modify selection.
      if (rowIds.includes(peekId)) {
        setRowSelectionModel([peekId]);
      }
    }
  }, [rowIds, peekId]);

  return (
    <StyledDataGrid
      rows={rows}
      initialState={{
        sorting: {
          sortModel: [{field: 'createdAt', sort: 'desc'}],
        },
      }}
      columnHeaderHeight={40}
      rowHeight={38}
      columns={columns}
      experimentalFeatures={{columnGrouping: true}}
      disableRowSelectionOnClick
      rowSelectionModel={rowSelectionModel}
      columnGroupingModel={columnGroupingModel}
    />
  );
};

const applyFilter = (
  allObjectVersions: WFObjectVersion[],
  effectiveFilter: WFHighLevelObjectVersionFilter
) => {
  return allObjectVersions.filter(ov => {
    if (
      effectiveFilter.typeVersions &&
      effectiveFilter.typeVersions.length > 0
    ) {
      if (
        !effectiveFilter.typeVersions.includes(
          ov.typeVersion().type().name() +
            ':' +
            ov.typeVersion().version().toString()
        )
      ) {
        return false;
      }
    }
    if (effectiveFilter.latest) {
      if (!ov.aliases().includes('latest')) {
        return false;
      }
    }
    if (effectiveFilter.typeCategory) {
      if (effectiveFilter.typeCategory !== ov.typeVersion().typeCategory()) {
        return false;
      }
    }
    if (
      effectiveFilter.inputToOpVersions &&
      effectiveFilter.inputToOpVersions.length > 0
    ) {
      const inputToOpVersions = ov.inputTo().map(i => i.opVersion());
      if (
        !inputToOpVersions.some(
          ovInner =>
            ovInner &&
            effectiveFilter.inputToOpVersions?.includes(
              ovInner.op().name() + ':' + ovInner.version()
            )
        )
      ) {
        return false;
      }
    }
    if (effectiveFilter.objectName) {
      if (effectiveFilter.objectName !== ov.object().name()) {
        return false;
      }
    }
    return true;
  });
};

const useObjectOptions = (
  allObjectVersions: WFObjectVersion[],
  highLevelFilter: WFHighLevelObjectVersionFilter
) => {
  const filtered = useMemo(() => {
    return applyFilter(
      allObjectVersions,
      _.omit(highLevelFilter, ['objectName'])
    );
  }, [allObjectVersions, highLevelFilter]);

  return useMemo(() => {
    return _.uniq(filtered.map(item => item.object().name())).sort((a, b) =>
      a.localeCompare(b)
    );
  }, [filtered]);
};

const useOpVersionOptions = (
  allObjectVersions: WFObjectVersion[],
  highLevelFilter: WFHighLevelObjectVersionFilter
) => {
  const filtered = useMemo(() => {
    return applyFilter(
      allObjectVersions,
      _.omit(highLevelFilter, ['inputToOpVersions'])
    );
  }, [allObjectVersions, highLevelFilter]);

  return useMemo(() => {
    const versions = filtered
      .flatMap(item => item.inputTo().map(i => i.opVersion()))
      .filter(v => v != null) as WFOpVersion[];

    return _.fromPairs(
      versions.map(v => {
        return [
          v.op().name() + ':' + v.version(),
          v.op().name() + ' (' + truncateID(v.version()) + ')',
        ];
      })
    );
  }, [filtered]);
};

const useTypeCategoryOptions = (
  allObjectVersions: WFObjectVersion[],
  highLevelFilter: WFHighLevelObjectVersionFilter
) => {
  const filtered = useMemo(() => {
    return applyFilter(
      allObjectVersions,
      _.omit(highLevelFilter, ['typeCategory'])
    );
  }, [allObjectVersions, highLevelFilter]);

  return useMemo(() => {
    return _.uniq(
      filtered.map(item => item.typeVersion().typeCategory())
    ).filter(v => v != null) as HackyTypeCategory[];
  }, [filtered]);
};

const useLatestOnlyOptions = (
  allObjectVersions: WFObjectVersion[],
  highLevelFilter: WFHighLevelObjectVersionFilter
) => {
  const filtered = useMemo(() => {
    return applyFilter(allObjectVersions, _.omit(highLevelFilter, ['latest']));
  }, [allObjectVersions, highLevelFilter]);

  return useMemo(() => {
    return _.uniq(filtered.map(item => item.aliases().includes('latest')));
  }, [filtered]);
};
