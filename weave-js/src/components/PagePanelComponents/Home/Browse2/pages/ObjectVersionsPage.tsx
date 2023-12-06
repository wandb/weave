import {OpenInNew} from '@mui/icons-material';
import {
  Autocomplete,
  Box,
  Checkbox,
  Chip,
  FormControl,
  IconButton,
  List,
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
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../context';
import {basicField} from './common/DataTable';
import {
  CallsLink,
  ObjectLink,
  ObjectVersionLink,
  OpVersionLink,
  TypeVersionLink,
} from './common/Links';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {HackyTypeCategory, WFObjectVersion} from './interface/wf/types';

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
  typeVersions?: string[];
  latestOnly?: boolean;
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
  const history = useHistory();
  const orm = useWeaveflowORMContext();
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
      if (effectiveFilter.typeVersions) {
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
      if (effectiveFilter.latestOnly) {
        if (!ov.aliases().includes('latest')) {
          return false;
        }
      }
      if (effectiveFilter.typeCategory) {
        if (effectiveFilter.typeCategory !== ov.typeVersion().typeCategory()) {
          return false;
        }
      }
      if (effectiveFilter.inputToOpVersions) {
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
      return true;
    });
  }, [
    allObjectVersions,
    effectiveFilter.inputToOpVersions,
    effectiveFilter.latestOnly,
    effectiveFilter.typeCategory,
    effectiveFilter.typeVersions,
  ]);
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'row',
      }}>
      <Box
        sx={{
          flex: '0 0 auto',
          height: '100%',
          width: '240px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
        }}>
        <Box
          sx={{
            pl: 2,
            pr: 1,
            height: 57,
            flex: '0 0 auto',
            borderBottom: '1px solid #e0e0e0',
            position: 'sticky',
            top: 0,
            zIndex: 1,
            backgroundColor: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
          Filters
          {Object.keys(props.frozenFilter ?? {}).length > 0 && (
            <IconButton
              size="small"
              onClick={() => {
                // TODO: use the route context
                history.push(
                  routerContext.objectVersionsUIUrl(
                    props.entity,
                    props.project,
                    effectiveFilter
                  )
                );
              }}>
              <OpenInNew />
            </IconButton>
          )}
        </Box>
        <List
          // dense
          sx={{width: '100%', maxWidth: 360, bgcolor: 'background.paper'}}>
          <ListItem
            secondaryAction={
              <Checkbox
                edge="end"
                checked={effectiveFilter.latestOnly}
                onChange={() => {
                  setFilter({
                    ...filter,
                    latestOnly: !effectiveFilter.latestOnly,
                  });
                }}
              />
            }
            disabled={Object.keys(props.frozenFilter ?? {}).includes(
              'latestOnly'
            )}
            disablePadding>
            <ListItemButton>
              <ListItemText primary={`Latest Only`} />
            </ListItemButton>
          </ListItem>
          <ListItem>
            <FormControl fullWidth>
              <Autocomplete
                size={'small'}
                // disablePortal
                // disableClearable
                // options={projects}
                // value={props.project}
                // onChange={(event, newValue) => {
                //   props.navigateToProject(newValue);
                // }}
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
                // disablePortal
                multiple
                disabled={Object.keys(props.frozenFilter ?? {}).includes(
                  'typeVersions'
                )}
                // disableClearable
                // options={projects}
                value={effectiveFilter.typeVersions ?? []}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    typeVersions: newValue,
                  });
                }}
                // open={true}
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
                // disablePortal
                // disableClearable
                // options={projects}
                // value={props.project}
                // onChange={(event, newValue) => {
                //   props.navigateToProject(newValue);
                // }}
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
        </List>
      </Box>
      <ObjectVersionsTable objectVersions={filteredObjectVersions} />
    </Box>
  );
};

const ObjectVersionsTable: React.FC<{
  objectVersions: WFObjectVersion[];
}> = props => {
  // const history = useHistory();
  // const routeContext = useWeaveflowRouteContext();
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
    basicField('typeCategory', 'Category', {
      width: 100,
      renderCell: cellParams => {
        if (cellParams.value == null) {
          return '';
        }

        const color = {
          model: 'success',
          dataset: 'info',
          // 'tune': 'warning',
        }[cellParams.row.typeCategory + ''];
        return (
          <Chip
            label={cellParams.row.typeCategory}
            size="small"
            color={color as any}
          />
        );
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
    basicField('description', 'Description'),
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
      // onCellClick={params => {
      //   // TODO: move these actions into a config
      //   if (params.field === 'id') {
      //     history.push(
      //       routeContext.objectVersionUIUrl(
      //         params.row.obj.entity(),
      //         params.row.obj.project(),
      //         params.row.object,
      //         params.row.version
      //       )
      //     );
      //   }
      // }}
    />
  );
};
