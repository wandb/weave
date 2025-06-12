import {Box, Drawer, Typography} from '@mui/material';
import {GridFilterModel} from '@mui/x-data-grid-pro';
import {styled} from '@mui/material/styles';
import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {
  MOON_250,
  MOON_350,
  TEAL_500,
} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {validateDatasetName} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/datasets/datasetNameValidation';
import {FilterPanel} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/filters/FilterPanel';
import {prepareFlattenedCallDataForTable} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/CallsTable';
import {useCallsTableColumns} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/callsTableColumns';
import {
  useOpVersionOptions,
  WFHighLevelCallFilter,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/callsTableFilter';
import {ALL_TRACES_OR_CALLS_REF_KEY} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/callsTableFilter';
import {
  getFilterByRaw,
  useFilterSortby,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/callsTableQuery';
import {OpSelector} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/CallsPage/OpSelector';
import {
  FieldName,
  typographyStyle,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/FormComponents';
import {LLMAsAJudgeScorerForm} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/ScorerForms/LLMAsAJudgeScorerForm';
import {queryToGridFilterModel} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/SavedViews/savedViewUtil';
import {useWFHooks} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/context';
import {
  useObjCreate,
  useRootObjectVersions,
  useScorerCreate,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {objectVersionKeyToRefUri} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/utilities';
import {
  ObjectVersionKey,
  ObjectVersionSchema,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {Radio} from '@wandb/weave/components';
import {Switch} from '@wandb/weave/components';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {parseRef} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {toast} from 'react-toastify';

const PAGE_SIZE = 10;
const PAGE_OFFSET = 0;

const StyledSliderInput = styled('div')<{progress: number}>(({progress}) => ({
  '& .slider-input': {
    '& input[type="range"]': {
      appearance: 'none',
      width: '100%',
      height: '8px',
      borderRadius: '4px',
      background: `linear-gradient(to right, ${TEAL_500} 0%, ${TEAL_500} ${progress}%, ${MOON_250} ${progress}%, ${MOON_250} 100%)`,
      outline: 'none',
      padding: 0,
      margin: '8px 0',
      '&::-webkit-slider-track': {
        width: '100%',
        height: '8px',
        borderRadius: '4px',
        background: 'transparent',
      },
      '&::-moz-range-track': {
        width: '100%',
        height: '8px',
        borderRadius: '4px',
        background: 'transparent',
      },
      '&::-webkit-slider-thumb': {
        appearance: 'none',
        width: '16px',
        height: '16px',
        borderRadius: '50%',
        background: '#fff',
        cursor: 'pointer',
        border: `1px solid ${MOON_350}`,
        boxShadow: '0 0 2px 0px rgba(0, 0, 0, 0.1)',
        transition: 'box-shadow 0.2s',
        '&:hover': {
          boxShadow: '0 0 8px 0px rgba(0, 0, 0, 0.2)',
        },
      },
      '&::-moz-range-thumb': {
        width: '12px',
        height: '12px',
        borderRadius: '50%',
        background: '#fff',
        cursor: 'pointer',
        border: `1px solid ${MOON_350}`,
        boxShadow: '0 0 2px 0px rgba(0, 0, 0, 0.1)',
        transition: 'box-shadow 0.2s',
        '&:hover': {
          boxShadow: '0 0 8px 0px rgba(0, 0, 0, 0.2)',
        },
      },
    },
  },
}));

const SCORER_FORMS: Map<
  string,
  React.ComponentType<{
    scorer: ObjectVersionSchema;
    onChange: (scorer: ObjectVersionSchema) => void;
    onValidationChange: (isValid: boolean) => void;
  }> | null
> = new Map([
  ['ValidJSONScorer', null],
  ['ValidXMLScorer', null],
  ['LLMAsAJudgeScorer', LLMAsAJudgeScorerForm],
]);

export const MonitorDrawerRouter = (props: CreateMonitorDrawerProps) => {
  if (props.monitor) {
    return (
      <CreateMonitorDrawerWithScorers {...props} monitor={props.monitor} /> // Repeating monitor to appease type checking
    );
  }
  return <CreateMonitorDrawer {...props} />;
};

const CreateMonitorDrawerWithScorers = (
  props: CreateMonitorDrawerProps & {monitor: ObjectVersionSchema}
) => {
  const scorerIds: string[] = useMemo(() => {
    return (
      props.monitor.val['scorers'].map(
        (scorerRefUri: string) => parseRef(scorerRefUri).artifactName
      ) || []
    );
  }, [props.monitor]);

  const {result: scorers, loading} = useRootObjectVersions({
    entity: props.entity,
    project: props.project,
    filter: {
      objectIds: scorerIds,
      latestOnly: true,
    },
  });
  return loading || !scorers ? (
    <WaveLoader size="huge" />
  ) : (
    <CreateMonitorDrawer {...props} scorers={scorers} />
  );
};

type CreateMonitorDrawerProps = {
  entity: string;
  project: string;
  open: boolean;
  onClose: () => void;
  monitor?: ObjectVersionSchema;
  scorers?: ObjectVersionSchema[];
};

export const CreateMonitorDrawer = ({
  entity,
  project,
  open,
  onClose,
  monitor,
  scorers: existingScorers,
}: CreateMonitorDrawerProps) => {
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [description, setDescription] = useState<string>(
    monitor?.val['description'] || ''
  );
  const [monitorName, setMonitorName] = useState<string>(
    monitor?.val['name'] || ''
  );
  const [samplingRate, setSamplingRate] = useState<number>(
    (monitor?.val['sampling_rate'] || 0.1) * 100
  );
  const [selectedOpVersionOption, setSelectedOpVersionOption] = useState<
    string[]
  >([]);
  const [filter, setFilter] = useState<WFHighLevelCallFilter>({
    opVersionRefs: monitor?.val['op_names'] || [],
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>(
    queryToGridFilterModel(monitor?.val['query']) || {
      items: [],
    }
  );
  const {useCalls} = useWFHooks();
  const [scorers, setScorers] = useState<ObjectVersionSchema[]>(
    existingScorers || []
  );
  const [scorerValids, setScorerValids] = useState<boolean[]>([]);
  const [active, setActive] = useState<boolean>(
    monitor?.val['active'] ?? true
  );
  const [validationType, setValidationType] = useState<'none' | 'json' | 'xml'>(() => {
    if (existingScorers?.some(s => s.val['_type'] === 'ValidJSONScorer')) return 'json';
    if (existingScorers?.some(s => s.val['_type'] === 'ValidXMLScorer')) return 'xml';
    return 'none';
  });
  const [llmAsJudgeEnabled, setLlmAsJudgeEnabled] = useState<boolean>(
    existingScorers ? existingScorers.some(s => s.val['_type'] === 'LLMAsAJudgeScorer') : true
  );
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const {sortBy, lowLevelFilter} = useFilterSortby(filter, {items: []}, [
    {field: 'started_at', sort: 'desc'},
  ]);

  useEffect(() => {
    setScorerValids(currentValids => currentValids.slice(0, scorers.length));
  }, [scorers.length]);

  useEffect(() => {
    const newScorers: ObjectVersionSchema[] = [];
    
    if (validationType === 'json') {
      newScorers.push({
        scheme: 'weave',
        weaveKind: 'object',
        entity,
        project,
        objectId: '',
        versionHash: '',
        path: '',
        versionIndex: 0,
        baseObjectClass: 'ValidJSONScorer',
        createdAtMs: Date.now(),
        val: {_type: 'ValidJSONScorer'},
      });
    } else if (validationType === 'xml') {
      newScorers.push({
        scheme: 'weave',
        weaveKind: 'object',
        entity,
        project,
        objectId: '',
        versionHash: '',
        path: '',
        versionIndex: 0,
        baseObjectClass: 'ValidXMLScorer',
        createdAtMs: Date.now(),
        val: {_type: 'ValidXMLScorer'},
      });
    }

    if (llmAsJudgeEnabled) {
      newScorers.push({
        scheme: 'weave',
        weaveKind: 'object',
        entity,
        project,
        objectId: '',
        versionHash: '',
        path: '',
        versionIndex: 0,
        baseObjectClass: 'LLMAsAJudgeScorer',
        createdAtMs: Date.now(),
        val: {_type: 'LLMAsAJudgeScorer'},
      });
    }

    setScorers(newScorers);
  }, [validationType, llmAsJudgeEnabled, entity, project]);

  const {result: callsResults, loading: callsLoading} = useCalls({
    entity,
    project,
    filter: lowLevelFilter,
    limit: PAGE_SIZE,
    offset: PAGE_OFFSET,
    sortBy,
  });

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
    '',
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

  const allScorersValid = useMemo(() => {
    return scorers.every((scorer, index) => {
      const hasForm = SCORER_FORMS.get(scorer.val['_type']) !== null;
      if (hasForm) {
        return scorerValids[index] === true;
      }
      return true; // No form, so it's valid
    });
  }, [scorers, scorerValids]);

  const enableCreateButton = useMemo(() => {
    return (
      monitorName.length > 0 &&
      selectedOpVersionOption.length > 0 &&
      scorers.length > 0 &&
      nameError === null &&
      allScorersValid
    );
  }, [
    monitorName,
    selectedOpVersionOption,
    scorers,
    nameError,
    allScorersValid,
  ]);

  const objCreate = useObjCreate();

  const scorerCreate = useScorerCreate();

  const createMonitor = useCallback(async () => {
    if (!enableCreateButton) {
      return;
    }

    setIsCreating(true);

    try {
      const scorerRefs = await Promise.all(
        scorers.map(async scorer => {
          let scorerVersionKey: ObjectVersionKey;
          if (scorer.versionHash) {
            scorerVersionKey = {
              scheme: 'weave',
              weaveKind: 'object',
              entity: scorer.entity,
              project: scorer.project,
              objectId: scorer.objectId,
              versionHash: scorer.versionHash,
              path: '',
            };
          } else {
            scorerVersionKey = await scorerCreate({
              entity,
              project,
              name: scorer.objectId,
              val: scorer.val,
            });
          }
          return objectVersionKeyToRefUri(scorerVersionKey);
        })
      );

      const mongoQuery = getFilterByRaw(filterModel);

      const opNames =
        selectedOpVersionOption.length === 1 &&
        selectedOpVersionOption[0] === ALL_TRACES_OR_CALLS_REF_KEY
          ? null
          : selectedOpVersionOption;

      const monitorObj = {
        _type: 'Monitor',
        name: monitorName,
        description,
        ref: null,
        _class_name: 'Monitor',
        _bases: ['Object', 'BaseModel'],
        op_names: opNames,
        query: mongoQuery ? {$expr: mongoQuery} : null,
        sampling_rate: samplingRate / 100,
        scorers: scorerRefs,
        active: active,
      };

      await objCreate({
        projectId: `${entity}/${project}`,
        objectId: monitorName,
        val: monitorObj,
        baseObjectClass: 'Monitor',
      });

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
    scorerCreate,
  ]);

  const scorerForms = useMemo(() => {
    return (
      <>
        {scorers.map((scorer, index) => {
          const ScorerForm = SCORER_FORMS.get(scorer.val['_type']);
          if (!ScorerForm) {
            return null;
          }
          return (
            <ScorerForm
              key={index}
              scorer={scorer}
              onChange={(newScorer: ObjectVersionSchema) =>
                setScorers(currentScorers =>
                  currentScorers.map((s, i) => (i === index ? newScorer : s))
                )
              }
              onValidationChange={(isValid: boolean) =>
                setScorerValids(currentValids => {
                  const nextValids = [...currentValids];
                  nextValids[index] = isValid;
                  return nextValids;
                })
              }
            />
          );
        })}
      </>
    );
  }, [scorers]);

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
            className="flex h-44 items-center justify-between border-b px-20"
            sx={{
              borderColor: 'divider',
            }}>
            <Typography
              variant="h6"
              className="text-xl font-semibold"
              sx={typographyStyle}>
              Create new monitor
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
          <Box className="flex flex-1 flex-col overflow-y-scroll pb-60 pt-20">
            {isCreating ? (
              <Box className="flex h-full flex-1 flex-col items-center justify-center">
                <WaveLoader size="huge" />
              </Box>
            ) : (
              <Box className="flex flex-grow flex-col gap-16">
                <Box className="flex flex-col gap-16 px-20">
                  {error && (
                    <Box
                      className="rounded-sm bg-red-300 text-red-600"
                      sx={typographyStyle}>
                      {error}
                    </Box>
                  )}
                  <Box>
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
                      className="mt-4 text-sm font-normal"
                      sx={{
                        ...typographyStyle,
                        color: 'text.secondary',
                      }}>
                      Valid monitor names must start with a letter or number and
                      can only contain letters, numbers, hyphens, and
                      underscores.
                    </Typography>
                  </Box>
                  <Box>
                    <FieldName name="Description" />
                    <TextArea
                      value={description}
                      rows={3}
                      placeholder="Enter a description for your monitor"
                      onChange={e => setDescription(e.target.value)}
                    />
                  </Box>
                  <Box>
                    <Box className="flex items-center gap-8">
                      <Switch.Root
                        checked={active}
                        onCheckedChange={setActive}
                        size="medium"
                      >
                        <Switch.Thumb size="medium" checked={active} />
                      </Switch.Root>
                      <span className="font-semibold">Active monitor</span>
                    </Box>
                  </Box>
                </Box>

                <Box className="flex flex-col gap-8 pt-16">
                  <Typography
                    sx={typographyStyle}
                    className="border-t border-moon-250 px-20 pb-8 pt-16 font-semibold uppercase tracking-wide text-moon-500">
                    Calls to monitor
                  </Typography>
                  <Box className="flex flex-col gap-16 px-20">
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
                      {selectedOpVersionOption.length > 0 ? (
                        <Box className="mt-4">
                          <FilterPanel
                            entity={entity}
                            project={project}
                            filterModel={filterModel}
                            setFilterModel={setFilterModel}
                            columnInfo={columns}
                            selectedCalls={[]}
                            clearSelectedCalls={() => {}}
                          />
                        </Box>
                      ) : (
                        <Typography
                          className="mt-4 text-sm font-normal"
                          sx={{
                            ...typographyStyle,
                            color: 'text.secondary',
                          }}>
                          Select an op to add additional filters.
                        </Typography>
                      )}
                    </Box>
                    <Box>
                      <FieldName name="Sampling rate" />
                      <Box className="flex items-center gap-12">
                        <StyledSliderInput className="w-full" progress={samplingRate}>
                          <SliderInput
                            value={samplingRate}
                            onChange={setSamplingRate}
                            min={0}
                            max={100}
                            step={10}
                            hasInput
                            className="w-full"
                          />
                        </StyledSliderInput>
                        <span style={typographyStyle}>%</span>
                      </Box>
                    </Box>
                  </Box>
                </Box>

                <Box className="flex flex-col gap-8 pt-16">
                  <Typography
                    sx={typographyStyle}
                    className="border-t border-moon-250 px-20 pb-8 pt-16 font-semibold uppercase tracking-wide text-moon-500">
                    Scorers
                  </Typography>
                  <Box className="flex flex-col gap-16 px-20">
                    <Box>
                      <FieldName name="Format validation" />
                      <Radio.Root
                        className="flex items-center gap-16"
                        aria-label="Validation type selection"
                        name="validation-type"
                        onValueChange={(value: 'none' | 'json' | 'xml') => setValidationType(value)}
                        value={validationType}>
                        
                        <label className="flex items-center">
                          <Radio.Item id="no-validation" value="none">
                            <Radio.Indicator />
                          </Radio.Item>
                          <span className="ml-6 cursor-pointer">No validation</span>
                        </label>
                        
                        <label className="flex items-center">
                          <Radio.Item id="json-validation" value="json">
                            <Radio.Indicator />
                          </Radio.Item>
                          <span className="ml-6 cursor-pointer">Valid JSON</span>
                        </label>
                        
                        <label className="flex items-center">
                          <Radio.Item id="xml-validation" value="xml">
                            <Radio.Indicator />
                          </Radio.Item>
                          <span className="ml-6 cursor-pointer">Valid XML</span>
                        </label>
                      </Radio.Root>
                    </Box>
                    
                    <Box className="flex items-center mt-8 gap-8">
                      <Switch.Root
                        checked={llmAsJudgeEnabled}
                        onCheckedChange={setLlmAsJudgeEnabled}
                        size="medium"
                      >
                        <Switch.Thumb size="medium" checked={llmAsJudgeEnabled} />
                      </Switch.Root>
                      <span className="font-semibold">Enable LLM-as-a-judge scoring</span>
                    </Box>
                  </Box>
                </Box>

                {scorerForms}
              </Box>
            )}
          </Box>
          <Box className="flex gap-8 border-t border-moon-250 p-20 py-16">
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
