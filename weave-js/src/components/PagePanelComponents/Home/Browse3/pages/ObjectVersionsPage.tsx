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
import {
  objectVersionKeyToRefUri,
  ObjectVersionSchema,
  useRootObjectVersions,
} from './wfReactInterface/interface';

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
      hideTabsIfSingle
      tabs={[
        {
          label: '',
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
  inputToOpVersionRefs?: string[];
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
  /**
   * Note to future devs: this page can be dramatically simplified and optimized:
   * 1. `inputToOpVersionRefs` is not used anywhere, so we can just drop it
   * 2. We should always show `latest` only, except when there is a name set and remove from filters
   * 3. `typeVersions` is not used an can be removed
   * 4. hardcode type category instead of the expensive scan over all object versions
   * 5. `name` is the last "filter" and should just be something that is displayed rather than a chosen filter.
   * All of this can remove the need for the heavy pass over all objects.
   */

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

  // const effectivelyLatestOnly = !(effectiveFilter.objectName || effectiveFilter.typeCategory)

  const filteredObjectVersions = useRootObjectVersions(
    props.entity,
    props.project,
    {
      category: effectiveFilter.typeCategory
        ? [effectiveFilter.typeCategory]
        : undefined,
      objectIds: effectiveFilter.objectName
        ? [effectiveFilter.objectName]
        : undefined,
      latestOnly: effectiveFilter.latest ? true : undefined,
    }
  );

  const objectOptions = useObjectOptions(allObjectVersions, effectiveFilter);

  // const typeCategoryOptions = useTypeCategoryOptions(
  //   allObjectVersions,
  //   effectiveFilter
  // );

  const opVersionOptions = useOpVersionOptions(
    allObjectVersions,
    effectiveFilter
  );

  // const latestOnlyOptions = useLatestOnlyOptions(
  //   allObjectVersions,
  //   effectiveFilter
  // );

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
          {/* <ListItem>
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
          </ListItem> */}

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
                value={effectiveFilter.inputToOpVersionRefs?.[0] ?? null}
                onChange={(event, newValue) => {
                  setFilter({
                    ...filter,
                    inputToOpVersionRefs: newValue ? [newValue] : [],
                  });
                }}
                getOptionLabel={option => {
                  return opVersionOptions[option] ?? option;
                }}
                options={Object.keys(opVersionOptions)}
              />
            </FormControl>
          </ListItem>
          {/* <ListItem
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
          </ListItem> */}
        </>
      }>
      <ObjectVersionsTable
        objectVersions={filteredObjectVersions.result ?? []}
        usingLatestFilter={effectiveFilter.latest}
      />
    </FilterLayoutTemplate>
  );
};

const ObjectVersionsTable: React.FC<{
  objectVersions: ObjectVersionSchema[];
  usingLatestFilter?: boolean;
}> = props => {
  const rows: GridRowsProp = useMemo(() => {
    return props.objectVersions.map((ov, i) => {
      return {
        id: objectVersionKeyToRefUri(ov),
        obj: ov,
        createdAt: ov.createdAtMs,
      };
    });
  }, [props.objectVersions]);
  const columns: GridColDef[] = [
    basicField('version', 'Object', {
      hideable: false,
      renderCell: cellParams => {
        // Icon to indicate navigation to the object version
        const obj: ObjectVersionSchema = cellParams.row.obj;
        return (
          <ObjectVersionLink
            entityName={obj.entity}
            projectName={obj.project}
            objectName={obj.objectId}
            version={obj.versionHash}
            versionIndex={obj.versionIndex}
            filePath={obj.path}
            refExtra={obj.refExtra}
          />
        );
      },
    }),
    basicField('typeCategory', 'Category', {
      width: 100,
      renderCell: cellParams => {
        const obj: ObjectVersionSchema = cellParams.row.obj;
        return <TypeVersionCategoryChip typeCategory={obj.category} />;
      },
    }),
    basicField('createdAt', 'Created', {
      width: 100,
      renderCell: cellParams => {
        const obj: ObjectVersionSchema = cellParams.row.obj;
        return <Timestamp value={obj.createdAtMs / 1000} format="relative" />;
      },
    }),
    ...(props.usingLatestFilter
      ? [
          basicField('peerVersions', 'Versions', {
            width: 100,
            renderCell: cellParams => {
              const obj: ObjectVersionSchema = cellParams.row.obj;
              return <PeerVersionsLink obj={obj} />;
            },
          }),
        ]
      : []),
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

const PeerVersionsLink: React.FC<{obj: ObjectVersionSchema}> = props => {
  const obj = props.obj;
  const objectVersions = useRootObjectVersions(obj.entity, obj.project, {
    objectIds: [obj.objectId],
  });
  return (
    <ObjectVersionsLink
      entity={obj.entity}
      project={obj.project}
      filter={{
        objectName: obj.objectId,
      }}
      versionCount={(objectVersions.result ?? []).length}
      neverPeek
      variant="secondary"
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
      const typeVersion = ov.typeVersion();
      if (!typeVersion) {
        return false;
      }
      if (
        !effectiveFilter.typeVersions.includes(
          typeVersion.type().name() + ':' + typeVersion.version().toString()
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
      if (effectiveFilter.typeCategory !== ov.typeVersion()?.typeCategory()) {
        return false;
      }
    }
    if (
      effectiveFilter.inputToOpVersionRefs &&
      effectiveFilter.inputToOpVersionRefs.length > 0
    ) {
      const inputToOpVersions = ov.inputTo().map(i => i.opVersion());
      if (
        !inputToOpVersions.some(
          ovInner =>
            ovInner &&
            effectiveFilter.inputToOpVersionRefs?.includes(ovInner.refUri())
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
          v.refUri(),
          v.op().name() + ' (' + truncateID(v.commitHash()) + ')',
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
      filtered.map(item => item.typeVersion()?.typeCategory())
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
