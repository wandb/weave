import {Box, Drawer, Typography} from '@mui/material';
import {GridFilterModel} from '@mui/x-data-grid-pro';
import SliderInput from '@wandb/weave/common/components/elements/SliderInput';
import {Button} from '@wandb/weave/components/Button';
import {StyledSliderInput} from '@wandb/weave/components/Form/StyledSliderInput';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
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
  useObjectVersion,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {
  ObjectVersionKey,
  ObjectVersionSchema,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {
  Root as SwitchRoot,
  Thumb as SwitchThumb,
} from '@wandb/weave/components/Switch';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {newMonitorCreated} from '@wandb/weave/integrations/analytics/monitorEvents';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {toast} from 'react-toastify';
import {useList} from 'react-use';

import {refUriToObjectVersionKey} from '../wfReactInterface/utilities';

const PAGE_SIZE = 10;
const PAGE_OFFSET = 0;

export interface ScorerFormProps {
  scorer: ObjectVersionSchema;
  onValidationChange: (valid: boolean) => void;
}

type ScorerFormType = React.ForwardRefExoticComponent<
  ScorerFormProps & React.RefAttributes<ScorerFormRef>
>;

export interface ScorerFormRef {
  saveScorer: () => Promise<string | undefined>;
}

const SCORER_FORMS: Map<string, ScorerFormType | null> = new Map([
  ['ValidJSONScorer', null],
  ['ValidXMLScorer', null],
  ['LLMAsAJudgeScorer', LLMAsAJudgeScorerForm],
]);

export const MonitorDrawerRouter = (props: MonitorFormDrawerProps) => {
  // Empty props.monitor.val['scorers'] should not happen but some such monitors
  // were persisted in the DB due to an early bug.
  // Fixed here: https://github.com/wandb/weave/pull/4945
  if (props.monitor && props.monitor.val['scorers'].length > 0) {
    return (
      <EditMonitorDrawerWithScorers {...props} monitor={props.monitor} /> // Repeating monitor to appease type checking
    );
  }
  return <MonitorFormDrawer {...props} />;
};

const EditMonitorDrawerWithScorers = (
  props: MonitorFormDrawerProps & {monitor: ObjectVersionSchema}
) => {
  // Supporting only one scorer for now
  const scorerVersionKey: ObjectVersionKey = useMemo(
    () => refUriToObjectVersionKey(props.monitor.val['scorers'][0])!,
    [props.monitor]
  );

  const {result: scorer, loading: scorerLoading} = useObjectVersion({
    key: scorerVersionKey,
  });

  return scorerLoading || !scorer ? (
    <WaveLoader size="huge" />
  ) : (
    <MonitorFormDrawer {...props} scorers={[scorer]} />
  );
};

type MonitorFormDrawerProps = {
  open: boolean;
  onClose: () => void;
  monitor?: ObjectVersionSchema;
  scorers?: ObjectVersionSchema[];
};

export const MonitorFormDrawer = ({
  open,
  onClose,
  monitor,
  scorers: existingScorers,
}: MonitorFormDrawerProps) => {
  const {entity, project} = useEntityProject();
  const [error, setError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [description, setDescription] = useState<string>('');
  const [monitorName, setMonitorName] = useState<string>('');
  const [samplingRate, setSamplingRate] = useState<number>(10);
  const [selectedOpVersionOption, setSelectedOpVersionOption] = useState<
    string[]
  >([]);
  const [filter, setFilter] = useState<WFHighLevelCallFilter>({
    opVersionRefs: [],
  });
  const [filterModel, setFilterModel] = useState<GridFilterModel>({
    items: [],
  });

  const {useCalls} = useWFHooks();

  const [scorers] = useList<ObjectVersionSchema>(
    existingScorers || [
      {
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
      },
    ]
  );

  const [scorerValids, {updateAt: updateScorerValidAt}] = useList<boolean>(
    existingScorers?.map(s => true) || [false]
  );

  const [active, setActive] = useState<boolean>(true);

  useEffect(() => {
    if (!monitor) {
      return;
    }
    setActive(monitor.val['active'] ?? false);
    setMonitorName(monitor.val['name'] ?? '');
    setDescription(monitor.val['description'] ?? '');
    setSamplingRate((monitor.val['sampling_rate'] || 0.1) * 100);
    setFilter({
      opVersionRefs: monitor.val['op_names'] || [],
    });
    setFilterModel(queryToGridFilterModel(monitor.val['query']) ?? {items: []});
    setSelectedOpVersionOption(monitor.val['op_names'] ?? []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monitor]);

  const [isCreating, setIsCreating] = useState<boolean>(false);

  const {sortBy, lowLevelFilter} = useFilterSortby(filter, {items: []}, [
    {field: 'started_at', sort: 'desc'},
  ]);

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

  const opVersionOptions = useOpVersionOptions(entity, project, {}, false);

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

  const scorerForms: ScorerFormType[] = useMemo(
    () =>
      scorers
        .map(scorer => SCORER_FORMS.get(scorer.val['_type']))
        .filter(f => !!f) as ScorerFormType[],
    [scorers]
  );

  const scorerFormRefs = useRef<ScorerFormRef[]>([]);

  // Ensure refs array matches subForms length
  useEffect(() => {
    scorerFormRefs.current = scorerFormRefs.current.slice(0, scorers.length);
  }, [scorerForms.length, scorers.length]);

  const objCreate = useObjCreate();

  const createMonitor = useCallback(async () => {
    if (!enableCreateButton) {
      return;
    }

    setIsCreating(true);

    try {
      const scorerRefs = await Promise.all(
        scorerFormRefs.current.map(async ref => await ref.saveScorer())
      );

      if (scorerRefs.some(ref => !ref)) {
        setError('Failed to create scorer');
        setIsCreating(false);
        return;
      }

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

      if (!monitor) {
        newMonitorCreated({entity, project, monitorName});
      }

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
    setIsCreating,
    monitor,
    onClose,
    active,
    enableCreateButton,
    entity,
    objCreate,
    project,
    scorerFormRefs,
  ]);

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
                  <Box className="flex items-center gap-8">
                    <SwitchRoot
                      size="small"
                      checked={active}
                      onCheckedChange={setActive}>
                      <SwitchThumb size="small" checked={active} />
                    </SwitchRoot>
                    <p className="font-semibold">Active monitor</p>
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
                        width="100%"
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
                        <StyledSliderInput
                          className="w-full"
                          progress={samplingRate}>
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

                {/*<Box className="flex flex-col gap-8 pt-16">
                  <Typography
                    sx={typographyStyle}
                    className="border-t border-moon-250 px-20 pb-8 pt-16 font-semibold uppercase tracking-wide text-moon-500">
                    Scorers
                  </Typography>
                  <Box className="flex flex-col gap-16 px-20">
                    <Box>
                      <FieldName name="Scorers" />
                      <Autocomplete
                        multiple
                        options={Array.from(SCORER_FORMS.keys())}
                        sx={{width: '100%'}}
                        value={scorers.map(
                          scorer => scorer.objectId || scorer.val['_type']
                        )}
                        onChange={(
                          unused,
                          newScorers: string | string[] | null
                        ) => {
                          if (newScorers === null) {
                            clearScorers();
                            clearScorerValids();
                            return;
                          }
                          const newScorerArray = _.isArray(newScorers)
                            ? (newScorers as string[])
                            : [newScorers as string];
                          setScorers(
                            newScorerArray.map(newScorer => ({
                              scheme: 'weave',
                              weaveKind: 'object',
                              entity,
                              project,
                              objectId: '',
                              versionHash: '',
                              path: '',
                              versionIndex: 0,
                              baseObjectClass: newScorer,
                              createdAtMs: Date.now(),
                              val: {_type: newScorer},
                            }))
                          );
                          setScorerValids(currentValids =>
                            currentValids.slice(0, newScorerArray.length)
                          );
                        }}
                      />
                    </Box>
                  </Box>
                </Box>*/}

                {scorerForms.map((Form: ScorerFormType, index: number) => (
                  <Form
                    key={index}
                    scorer={scorers[index]}
                    onValidationChange={(isValid: boolean) =>
                      updateScorerValidAt(index, isValid)
                    }
                    ref={(el: ScorerFormRef) =>
                      (scorerFormRefs.current[index] = el)
                    }
                  />
                ))}
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
