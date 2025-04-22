import {Box, Drawer, Typography} from '@mui/material';
import {GridFilterModel} from '@mui/x-data-grid-pro';
import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {Button} from '@wandb/weave/components/Button';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {ToggleButtonGroup} from '@wandb/weave/components/ToggleButtonGroup';
import React, {useCallback, useMemo, useState} from 'react';
import {toast} from 'react-toastify';

import {TextArea} from '../../../../../Form/TextArea';
import {TextField} from '../../../../../Form/TextField';
import {validateDatasetName} from '../../datasets/datasetNameValidation';
import {FilterPanel} from '../../filters/FilterPanel';
import {prepareFlattenedCallDataForTable} from '../CallsPage/CallsTable';
import {useCallsTableColumns} from '../CallsPage/callsTableColumns';
import {
  useOpVersionOptions,
  WFHighLevelCallFilter,
} from '../CallsPage/callsTableFilter';
import {getFilterByRaw,useFilterSortby} from '../CallsPage/callsTableQuery';
import {Autocomplete,OpSelector} from '../CallsPage/OpSelector';
import {useWFHooks} from '../wfReactInterface/context';
import {useObjCreate} from '../wfReactInterface/tsDataModelHooks';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {queryToGridFilterModel} from './saveViewUtil';

const typographyStyle = {fontFamily: 'Source Sans Pro'};

const PAGE_SIZE = 10;
const PAGE_OFFSET = 0;

enum BuiltInScorers {
  ValidJSONScorer = 'ValidJSONScorer',
  PydanticScorer = 'PydanticScorer',
}

export const CreateMonitorDrawer = ({
  entity,
  project,
  open,
  onClose,
  monitor,
}: {
  entity: string;
  project: string;
  open: boolean;
  onClose: () => void;
  monitor?: ObjectVersionSchema;
}) => {
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [description, setDescription] = useState<string>('');
  const [monitorName, setMonitorName] = useState<string>('');
  const [samplingRate, setSamplingRate] = useState<number>(10);
  const [selectedOpVersionOption, setSelectedOpVersionOption] = useState<
    string[]
  >([]);
  const [filter, setFilter] = useState<WFHighLevelCallFilter>({});
  const [filterModel, setFilterModel] = useState<GridFilterModel>({items: []});
  const {useCalls} = useWFHooks();
  const [scorers, setScorers] = useState<BuiltInScorers[]>([]);
  const [active, setActive] = useState<boolean>(false);
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const {sortBy, lowLevelFilter} = useFilterSortby(filter, {items: []}, [
    {field: 'started_at', sort: 'desc'},
  ]);
  useMemo(() => {
    setMonitorName(monitor?.val['name'] || '');
    setDescription(monitor?.val['description'] || '');
    setSamplingRate((monitor?.val['sampling_rate'] || 0.1) * 100);
    setFilter({opVersionRefs: monitor?.val['op_names'] || []});
    setScorers(monitor?.val['scorers'] || []);
    setActive(monitor?.val['active'] || false);
    setFilterModel(
      queryToGridFilterModel(monitor?.val['query']) || {
        items: [],
      }
    );
  }, [monitor, setMonitorName]);

  const {result: callsResults, loading: callsLoading} = useCalls(
    entity,
    project,
    lowLevelFilter,
    PAGE_SIZE,
    PAGE_OFFSET,
    sortBy
  );

  const tableData = useMemo(() => {
    if (callsLoading || callsResults === null) {
      return [];
    }
    return prepareFlattenedCallDataForTable(callsResults);
  }, [callsResults, callsLoading]);

  const {columns} = useCallsTableColumns(
    entity,
    project,
    filter,
    tableData,
    new Set(),
    () => {},
    () => {},
    () => false
  );

  const handleNameChange = useCallback(
    (value: string) => {
      setMonitorName(value);
      const validationResult = validateDatasetName(value);
      setNameError(validationResult.error);
    },
    [setNameError]
  );

  const opVersionOptions = useOpVersionOptions(entity, project, {});

  useMemo(() => {
    setSelectedOpVersionOption(filter.opVersionRefs ?? []);
  }, [filter]);

  const enableCreateButton = useMemo(() => {
    return (
      monitorName.length > 0 &&
      selectedOpVersionOption.length > 0 &&
      scorers.length > 0 &&
      nameError === null
    );
  }, [monitorName, selectedOpVersionOption, scorers, nameError]);

  const objCreate = useObjCreate();

  const createMonitor = useCallback(async () => {
    if (!enableCreateButton) {
      return;
    }

    setIsCreating(true);

    const mongoQuery = getFilterByRaw(filterModel);

    const monitorObj = {
      _type: 'Monitor',
      name: monitorName,
      description,
      ref: null,
      _class_name: 'Monitor',
      _bases: ['Object', 'BaseModel'],
      op_names: selectedOpVersionOption,
      query: {$expr: mongoQuery},
      sampling_rate: samplingRate / 100,
      scorers,
      active: active,
    };

    try {
      await objCreate(`${entity}/${project}`, monitorName, monitorObj);
      setIsCreating(false);
      toast.success(
        `Monitor ${monitorName} ${monitor ? 'updated' : 'created'}`,
        {
          autoClose: 2500,
        }
      );
      onClose();
    } catch (objCreateError) {
      setError('Failed to create monitor');
    }
  }, [
    monitorName,
    description,
    selectedOpVersionOption,
    filterModel,
    samplingRate,
    scorers,
    setIsCreating,
    monitor,
    onClose,
    active,
    enableCreateButton,
    entity,
    objCreate,
    project,
  ]);
  console.log(filterModel);
  return (
    <Drawer
      open={open}
      anchor="right"
      onClose={onClose}
      sx={{
        '& .MuiDrawer-paper': {
          width: '500px',
          position: 'fixed',
        },
      }}>
      <Tailwind style={{height: '100%'}}>
        <Box className="flex h-full flex-col pt-60">
          <Box
            className="flex h-56 items-center justify-between border-b px-20 py-8"
            sx={{
              borderColor: 'divider',
            }}>
            <Typography
              variant="h6"
              className="text-xl font-semibold"
              sx={typographyStyle}>
              Create monitor
            </Typography>
            <Box className="flex gap-2">
              <Button
                onClick={onClose}
                variant="ghost"
                icon="close"
                tooltip="Close"
              />
            </Box>
          </Box>
          <Box className="flex flex-1 flex-col overflow-y-scroll px-20 pb-24 pt-12">
            {isCreating ? (
              <Box className="flex h-full flex-1 flex-col items-center justify-center">
                <WaveLoader size="huge" />
              </Box>
            ) : (
              <Box className="flex flex-grow flex-col gap-16">
                <Box className="flex flex-col gap-16">
                  {error && (
                    <Box
                      className="mb-2 rounded-sm bg-red-300 text-red-600"
                      sx={typographyStyle}>
                      {error}
                    </Box>
                  )}
                  <Box className="mb-2">
                    <FieldName name="Name" />
                    <TextField
                      value={monitorName}
                      placeholder="Enter a name for your monitor"
                      errorState={nameError !== null}
                      onChange={handleNameChange}
                    />
                    {nameError && (
                      <Typography
                        className="mt-1 text-sm"
                        sx={{
                          ...typographyStyle,
                          color: 'error.main',
                        }}>
                        {nameError}
                      </Typography>
                    )}
                    <Typography
                      className="mt-1 text-sm font-normal"
                      sx={{
                        ...typographyStyle,
                        color: 'text.secondary',
                      }}>
                      Valid monitor names must start with a letter or number and
                      can only contain letters, numbers, hyphens, and
                      underscores.
                    </Typography>
                  </Box>
                  <Box className="mb-2">
                    <FieldName name="Description" />
                    <TextArea
                      value={description}
                      rows={3}
                      placeholder="Enter a description for your monitor"
                      onChange={e => setDescription(e.target.value)}
                    />
                  </Box>
                  <Box className="mb-2">
                    <FieldName name="Active" />
                    <ToggleButtonGroup
                      value={active ? 'active' : 'inactive'}
                      options={[{value: 'active'}, {value: 'inactive'}]}
                      onValueChange={value => setActive(value === 'active')}
                      size="medium"
                    />
                  </Box>
                </Box>
                <Box className="flex flex-col gap-8">
                  <Typography
                    sx={typographyStyle}
                    className="text-lg font-semibold">
                    Calls to monitor
                  </Typography>
                  <Box className="flex flex-col gap-16">
                    <Box>
                      <FieldName name="Operations" />
                      <OpSelector
                        multiple
                        filter={{traceRootsOnly: false}}
                        selectedOpVersionOption={selectedOpVersionOption}
                        opVersionOptions={opVersionOptions}
                        setFilter={f =>
                          setFilter({...f, traceRootsOnly: false})
                        }
                        frozenFilter={undefined}
                        sx={{width: '100%', height: undefined}}
                      />
                    </Box>
                    <Box>
                      <FieldName name="Additional filters" />
                      {selectedOpVersionOption.length > 0 ? (
                        <FilterPanel
                          entity={entity}
                          project={project}
                          filterModel={filterModel}
                          setFilterModel={setFilterModel}
                          columnInfo={columns}
                          selectedCalls={[]}
                          clearSelectedCalls={() => {}}
                        />
                      ) : (
                        <Typography
                          className="mt-1 text-sm font-normal"
                          sx={{
                            ...typographyStyle,
                            color: 'text.secondary',
                          }}>
                          Select an op to add filters.
                        </Typography>
                      )}
                    </Box>
                    <Box>
                      <FieldName name="Sampling rate" />
                      <Box className="flex items-center gap-12">
                        <SliderInput
                          value={samplingRate}
                          onChange={setSamplingRate}
                          min={0}
                          max={100}
                          step={1}
                          hasInput
                          className="w-full"
                        />
                        <span style={typographyStyle}>%</span>
                      </Box>
                    </Box>
                  </Box>
                </Box>
                <Box className="flex flex-col gap-8">
                  <Typography
                    sx={typographyStyle}
                    className="text-lg font-semibold">
                    Scorers to apply to selected calls
                  </Typography>
                  <Box className="flex flex-col gap-16">
                    <Box>
                      <FieldName name="Scorers" />
                      <Autocomplete
                        multiple
                        options={Object.values(BuiltInScorers)}
                        sx={{width: '100%'}}
                        value={scorers}
                        onChange={(_, newScorers: string | string[] | null) =>
                          setScorers((newScorers as BuiltInScorers[]) ?? [])
                        }
                      />
                    </Box>
                  </Box>
                </Box>
              </Box>
            )}
          </Box>
          <Box className="flex gap-16 px-24 py-20">
            <Button
              variant="secondary"
              onClick={onClose}
              twWrapperStyles={{flexGrow: 1}}
              className="w-full">
              Cancel
            </Button>
            <Button
              disabled={!enableCreateButton}
              variant="primary"
              onClick={createMonitor}
              twWrapperStyles={{flexGrow: 1}}
              className="w-full">
              {monitor ? 'Update monitor' : 'Create monitor'}
            </Button>
          </Box>
        </Box>
      </Tailwind>
    </Drawer>
  );
};

const FieldName = ({name}: {name: string}) => {
  return (
    <Typography sx={typographyStyle} className="mb-8 font-semibold">
      {name}
    </Typography>
  );
};
