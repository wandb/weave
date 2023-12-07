import {
  Autocomplete,
  Box,
  Checkbox,
  Chip,
  FormControl,
  ListItem,
  ListItemButton,
  ListItemText,
  TextField,
} from '@mui/material';
import {
  DataGridPro,
  GridColDef,
  GridColumnGroupingModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import moment from 'moment';
import React, {useEffect, useMemo, useState} from 'react';

import {useWeaveflowRouteContext} from '../context';
import {basicField} from './common/DataTable';
import {
  CallsLink,
  ObjectLink,
  ObjectVersionLink,
  OpVersionLink,
  TypeVersionLink,
} from './common/Links';
import {FilterLayoutTemplate} from './common/SimpleFilterableDataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {TypeVersionCategoryChip} from './common/TypeVersionCategoryChip';
import {useWeaveflowORMContext} from './interface/wf/context';
import {HackyTypeCategory, WFObjectVersion} from './interface/wf/types';
import {useMutation} from '@apollo/client';
import {UPDATE_ARTIFACT_DESCRIPTION} from './interface/gql';
import {useUpdateObjectVersionDescription} from './interface/dataModel';

export const ObjectVersionsPage: React.FC<{
  entity: string;
  project: string;
  initialFilter?: WFHighLevelObjectVersionFilter;
}> = props => {
  return (
    <SimplePageLayout
      title="Object Versions"
      tabs={[
        {
          label: 'All',
          content: <FilterableObjectVersionsTable {...props} />,
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
}> = props => {
  const routerContext = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext();

  const objectOptions = useMemo(() => {
    const objects = orm.projectConnection.objects();
    const options = objects.map(v => v.name());
    return options;
  }, [orm.projectConnection]);

  const opVersionOptions = useMemo(() => {
    const versions = orm.projectConnection.opVersions();
    // Note: this excludes the named ones without op versions
    const options = versions.map(v => v.op().name() + ':' + v.version());
    return options;
  }, [orm.projectConnection]);
  const typeCategoryOptions = useMemo(() => {
    return orm.projectConnection.typeCategories();
  }, [orm.projectConnection]);
  const typeVersionOptions = useMemo(() => {
    const versions = orm.projectConnection.typeVersions();
    const options = versions.map(
      v => v.type().name() + ':' + v.version().toString()
    );
    return options;
  }, [orm]);
  const [filter, setFilter] = useState<WFHighLevelObjectVersionFilter>(
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
  const allObjectVersions = useMemo(() => {
    return orm.projectConnection.objectVersions();
  }, [orm.projectConnection]);
  const filteredObjectVersions = useMemo(() => {
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
  }, [
    allObjectVersions,
    effectiveFilter.inputToOpVersions,
    effectiveFilter.latest,
    effectiveFilter.objectName,
    effectiveFilter.typeCategory,
    effectiveFilter.typeVersions,
  ]);
  return (
    <FilterLayoutTemplate
      filterPopoutTargetUrl={routerContext.objectVersionsUIUrl(
        props.entity,
        props.project,
        effectiveFilter
      )}
      filterListItems={
        <>
          <ListItem
            secondaryAction={
              <Checkbox
                edge="end"
                checked={effectiveFilter.latest}
                onChange={() => {
                  setFilter({
                    ...filter,
                    latest: !effectiveFilter.latest,
                  });
                }}
              />
            }
            disabled={Object.keys(props.frozenFilter ?? {}).includes('latest')}
            disablePadding>
            <ListItemButton>
              <ListItemText primary={`Latest Only`} />
            </ListItemButton>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'objectName'
                )}
                renderInput={params => (
                  <TextField {...params} label="Object Name" />
                )}
                value={effectiveFilter.objectName}
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
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'typeCategory'
                )}
                renderInput={params => (
                  <TextField {...params} label="Type Category" />
                )}
                value={effectiveFilter.typeCategory}
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
                multiple
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'typeVersions'
                )}
                value={effectiveFilter.typeVersions ?? []}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    typeVersions: newValue,
                  });
                }}
                renderInput={params => (
                  <TextField {...params} label="Type Versions" />
                )}
                options={typeVersionOptions}
              />
            </FormControl>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                multiple
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'inputToOpVersions'
                )}
                renderInput={params => (
                  <TextField {...params} label="Input To" />
                )}
                value={effectiveFilter.inputToOpVersions ?? []}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    inputToOpVersions: newValue,
                  });
                }}
                options={opVersionOptions}
              />
            </FormControl>
          </ListItem>
        </>
      }>
      <ObjectVersionsTable objectVersions={filteredObjectVersions} />
    </FilterLayoutTemplate>
  );
};

const ObjectVersionsTable: React.FC<{
  objectVersions: WFObjectVersion[];
}> = props => {
  // const history = useHistory();
  // const routeContext = useWeaveflowRouteContext();
  const updateDescription = useUpdateObjectVersionDescription();
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
        description: ov.description(),
        versionIndex: ov.versionIndex(),
        createdAt: ov.createdAtMs(),
        isLatest: ov.aliases().includes('latest'),
      };
    });
  }, [props.objectVersions]);
  const columns: GridColDef[] = [
    basicField('createdAt', 'Created At', {
      width: 150,
      renderCell: params => {
        return moment(params.value as number).format('YYYY-MM-DD HH:mm:ss');
      },
    }),

    basicField('version', 'Version', {
      renderCell: params => {
        // Icon to indicate navigation to the object version
        return (
          <ObjectVersionLink
            objectName={params.row.obj.object().name()}
            version={params.row.obj.version()}
            hideName
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
    basicField('object', 'Object', {
      renderCell: params => <ObjectLink objectName={params.value as string} />,
    }),

    basicField('typeVersion', 'Type Version', {
      renderCell: params => (
        <TypeVersionLink
          typeName={params.row.obj.typeVersion().type().name()}
          version={params.row.obj.typeVersion().version()}
        />
      ),
    }),
    basicField('inputTo', 'Input To', {
      width: 100,
      renderCell: params => {
        if (params.value === 0) {
          return '';
        }

        return (
          <CallsLink
            entity={params.row.obj.entity()}
            project={params.row.obj.project()}
            callCount={params.value}
            filter={{
              inputObjectVersions: [
                params.row.obj.object().name() + ':' + params.row.obj.version(),
              ],
            }}
          />
        );
      },
    }),
    basicField('outputFrom', 'Output From', {
      width: 100,
      renderCell: params => {
        if (!params.value) {
          return '';
        }
        const outputFrom = params.row.obj.outputFrom();
        if (outputFrom.length === 0) {
          return '';
        }
        // if (outputFrom.length === 1) {
        return (
          <OpVersionLink
            opName={outputFrom[0].opVersion().op().name()}
            version={outputFrom[0].opVersion().version()}
          />
        );
        // }
        // return (
        //   <Link to={''}>
        //     {outputFrom.length} calls (TODO: link with filter)
        //   </Link>
        // );
      },
    }),
    basicField('description', 'Description', {
      editable: true,
    }),
    basicField('versionIndex', 'Version', {
      width: 100,
    }),

    basicField('isLatest', 'Latest', {
      width: 100,
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
    }),
  ];
  const columnGroupingModel: GridColumnGroupingModel = [];
  return (
    <DataGridPro
      rows={rows}
      initialState={{
        sorting: {
          sortModel: [{field: 'createdAt', sort: 'desc'}],
        },
      }}
      rowHeight={38}
      columns={columns}
      experimentalFeatures={{columnGrouping: true}}
      disableRowSelectionOnClick
      columnGroupingModel={columnGroupingModel}
      onCellEditStop={(params, event) => {
        if (params.field === 'description') {
          const newDesc = (event as any).target.value;
          updateDescription(
            params.row.obj.entity(),
            params.row.obj.project(),
            params.row.obj.object().name(),
            params.row.obj.version(),
            newDesc
          );
        }
      }}
    />
  );
};
