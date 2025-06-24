import {Box} from '@mui/material';
import {MOON_50, MOON_200} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Icon, IconName} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {parseWeaveRef} from '@wandb/weave/react';
import React, {useCallback, useMemo, useRef, useState} from 'react';

import {ReusableDrawer} from '../../ReusableDrawer';
import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {ScorerFormRef} from '../MonitorsPage/MonitorFormDrawer';
import {LLMAsAJudgeScorerForm} from '../MonitorsPage/ScorerForms/LLMAsAJudgeScorerForm';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {
  EvaluationExplorerPageProvider,
  useEvaluationExplorerPageContext,
} from './context';
import {NewDatasetEditor} from './DatasetEditor';
import {clientBound, hookify} from './hooks';
import {
  getLatestDatasetRefs,
  getLatestEvaluationRefs,
  getScorerByRef,
} from './query';

const HEADER_HEIGHT_PX = 44;
const BORDER_COLOR = MOON_200;
const SECONDARY_BACKGROUND_COLOR = MOON_50;

type EvaluationExplorerPageProps = {
  entity: string;
  project: string;
};

export const EvaluationExplorerPage = (props: EvaluationExplorerPageProps) => {
  return (
    <SimplePageLayoutWithHeader
      title="EvaluationExplorer"
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: (
            <EvaluationExplorerPageProvider>
              <EvaluationExplorerPageInner {...props} />
            </EvaluationExplorerPageProvider>
          ),
        },
      ]}
      headerExtra={null}
    />
  );
};

const EvaluationExplorerPageInner: React.FC<EvaluationExplorerPageProps> = ({
  entity,
  project,
}) => {
  const {config} = useEvaluationExplorerPageContext();
  const [newDatasetEditorMode, setNewDatasetEditorMode] = useState<
    'new-empty' | 'new-file'
  >('new-empty');
  const datasetEditorMode = useMemo(() => {
    if (
      config.evaluationDefinition.properties.dataset.originalSourceRef == null
    ) {
      return newDatasetEditorMode;
    }
    return 'existing';
  }, [config, newDatasetEditorMode]);
  console.log(config);
  return (
    <Row>
      <ConfigPanel
        entity={entity}
        project={project}
        setNewDatasetEditorMode={setNewDatasetEditorMode}
      />
      <Column style={{flex: '1 1 600px', overflow: 'hidden'}}>
        <Header>Dataset</Header>
        {datasetEditorMode === 'new-empty' && (
          <NewDatasetEditor entity={entity} project={project} />
        )}
        {datasetEditorMode === 'new-file' && (
          <NewDatasetEditor entity={entity} project={project} useFilePicker />
        )}
        {datasetEditorMode === 'existing' && <div>Not implemented</div>}
      </Column>
    </Row>
  );
};

const ConfigPanel: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  return (
    <Column
      style={{
        maxWidth: '500px',
        minWidth: '300px',
        flex: '1 1 400px',
        borderRight: `1px solid ${BORDER_COLOR}`,
        backgroundColor: SECONDARY_BACKGROUND_COLOR,
      }}>
      <Header>
        <span>Configuration</span>
        <Button
          icon="settings-parameters"
          size="small"
          variant="secondary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}
        />
      </Header>
      <Column style={{flex: 1, overflowY: 'auto'}}>
        <EvaluationConfigSection
          entity={entity}
          project={project}
          setNewDatasetEditorMode={setNewDatasetEditorMode}
        />
        <ModelsConfigSection entity={entity} project={project} />
      </Column>
      <Footer>
        <Button
          icon="save"
          variant="secondary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}>
          Save all
        </Button>
        <Button
          icon="play"
          variant="primary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}>
          Run eval
        </Button>
      </Footer>
    </Column>
  );
};

const ConfigSection: React.FC<{
  title: string;
  icon: IconName;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({title, icon, style, children}) => {
  return (
    <Column style={{padding: '8px 16px 16px 16px', flex: 0, ...style}}>
      <Row
        style={{
          alignItems: 'center',
          flex: 0,
          fontWeight: 600,
          paddingBottom: '8px',
        }}>
        <Icon name={icon} />
        <span style={{marginLeft: '4px'}}>{title}</span>
      </Row>
      {children}
    </Column>
  );
};

// Shared components

const Header: React.FC<{children?: React.ReactNode}> = ({children}) => {
  return (
    <div
      style={{
        height: HEADER_HEIGHT_PX,
        borderBottom: `1px solid ${BORDER_COLOR}`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        fontWeight: 600,
        fontSize: '18px',
        justifyContent: 'space-between',
        flex: `0 0 ${HEADER_HEIGHT_PX}px`,
      }}>
      {children}
    </div>
  );
};

const Footer: React.FC<{children?: React.ReactNode}> = ({children}) => {
  return (
    <div
      style={{
        height: HEADER_HEIGHT_PX,
        borderTop: `1px solid ${BORDER_COLOR}`,
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        fontWeight: 600,
        fontSize: '18px',
        justifyContent: 'space-between',
      }}>
      {children}
    </div>
  );
};

//  Generic components for layout

const Row: React.FC<{
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({style, children}) => {
  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'row',
        height: '100%',
        width: '100%',
        flex: 1,
        ...style,
      }}>
      {children}
    </Box>
  );
};

const Column: React.FC<{
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({style, children}) => {
  return (
    <Box
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        flex: 1,
        ...style,
      }}>
      {children}
    </Box>
  );
};

const LoadingSelect: typeof Select = props => {
  return <Select isDisabled placeholder="Loading..." {...props} />;
};

// Specialized Components

const EvaluationConfigSection: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  return (
    <ConfigSection title="Evaluation" icon="baseline-alt">
      <EvaluationPicker entity={entity} project={project} />
      <Column
        style={{
          flex: 0,
          borderLeft: `1px solid ${BORDER_COLOR}`,
          marginTop: '16px',
        }}>
        <Row style={{padding: '8px 0px 8px 16px'}}>
          <TextField
            value={config.evaluationDefinition.properties.name}
            placeholder="Evaluation Name"
            onChange={value => {
              editConfig(draft => {
                draft.evaluationDefinition.properties.name = value;
              });
            }}
          />
        </Row>
        <Row style={{padding: '8px 0px 16px 16px'}}>
          <TextArea
            value={config.evaluationDefinition.properties.description}
            placeholder="Evaluation Description"
            onChange={e => {
              editConfig(draft => {
                draft.evaluationDefinition.properties.description =
                  e.target.value;
              });
            }}
          />
        </Row>
        <DatasetConfigSection
          entity={entity}
          project={project}
          setNewDatasetEditorMode={setNewDatasetEditorMode}
        />
        <ScorersConfigSection entity={entity} project={project} />
      </Column>
    </ConfigSection>
  );
};

const useLatestEvaluationRefs = clientBound(hookify(getLatestEvaluationRefs));
const EvaluationPicker: React.FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  const refsQuery = useLatestEvaluationRefs(entity, project);
  const newEvaluationOption = useMemo(() => {
    return {
      label: 'New Evaluation',
      value: 'new-evaluation',
    };
  }, []);
  const selectOptions = useMemo(() => {
    return [
      newEvaluationOption,
      ...(refsQuery.data?.map(ref => ({
        label: ref,
      })) ?? []),
    ];
  }, [refsQuery.data, newEvaluationOption]);
  const selectedValue = useMemo(() => {
    return selectOptions[0];
  }, [selectOptions]);

  if (refsQuery.loading) {
    return <LoadingSelect />;
  }

  return (
    <Select
      options={selectOptions}
      value={selectedValue}
      onChange={option => {
        console.log(option);
        console.error('TODO: Implement me');
      }}
    />
  );
};

const DatasetConfigSection: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  return (
    <ConfigSection
      title="Dataset"
      icon="table"
      style={{
        paddingTop: '0px',
        paddingRight: '0px',
      }}>
      <DatasetPicker
        entity={entity}
        project={project}
        setNewDatasetEditorMode={setNewDatasetEditorMode}
      />
    </ConfigSection>
  );
};

const useLatestDatasetRefs = clientBound(hookify(getLatestDatasetRefs));
const DatasetPicker: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  const refsQuery = useLatestDatasetRefs(entity, project);

  const newDatasetOptions = useMemo(() => {
    return [
      {
        label: 'Start from scratch',
        value: 'new-empty',
      },
      {
        label: 'Upload a file',
        value: 'new-file',
      },
    ];
  }, []);

  const selectOptions = useMemo(() => {
    return [
      {
        label: 'Create new dataset',
        options: newDatasetOptions,
      },
      {
        label: 'Load existing dataset',
        options:
          refsQuery.data?.map(ref => ({
            label: ref,
            value: ref,
          })) ?? [],
      },
    ];
  }, [refsQuery.data, newDatasetOptions]);

  const [selectedValue, setSelectedValue] = useState(
    selectOptions[0].options[0]
  );

  if (refsQuery.loading) {
    return <LoadingSelect />;
  }

  return (
    <Select
      blurInputOnSelect
      options={selectOptions}
      value={selectedValue}
      onChange={option => {
        if (option?.value === 'new-empty') {
          setNewDatasetEditorMode('new-empty');
        } else if (option?.value === 'new-file') {
          setNewDatasetEditorMode('new-file');
        } else {
          console.error('TODO: Implement me');
        }
        if (option) {
          setSelectedValue(option);
        }
      }}
    />
  );
};

const newScorerOption = {
  label: 'New Scorer',
  value: 'new-scorer',
};

const ScorersConfigSection: React.FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();

  const [currentlyEditingScorerNdx, setCurrentlyEditingScorerNdx] = useState<
    number | null
  >(null);

  const scorers = useMemo(() => {
    return config.evaluationDefinition.properties.scorers;
  }, [config]);

  const addScorer = useCallback(() => {
    editConfig(draft => {
      draft.evaluationDefinition.properties.scorers.push({
        originalSourceRef: null,
      });
    });
  }, [editConfig]);

  const scorerOptions = useMemo(() => {
    return [newScorerOption];
  }, []);

  const deleteScorer = useCallback(
    (scorerNdx: number) => {
      editConfig(draft => {
        draft.evaluationDefinition.properties.scorers.splice(scorerNdx, 1);
      });
    },
    [editConfig]
  );

  console.log('currentlyEditingScorerNdx', currentlyEditingScorerNdx);

  return (
    <ConfigSection
      title="Scorers"
      icon="type-number-alt"
      style={{
        paddingBottom: '0px',
        paddingRight: '0px',
      }}>
      <Column style={{gap: '8px'}}>
        {scorers.map((scorer, scorerNdx) => {
          let selectedOption = newScorerOption;
          const options = [...scorerOptions];
          if (scorer.originalSourceRef) {
            const ref = parseWeaveRef(scorer.originalSourceRef);
            const name = `${ref.artifactName} (${ref.artifactVersion.slice(
              0,
              4
            )})`;
            selectedOption = {
              label: name,
              value: scorer.originalSourceRef,
            };
            options.unshift(selectedOption);
          }
          return (
            <Row key={scorerNdx} style={{alignItems: 'center', gap: '8px'}}>
              <div style={{flex: 1}}>
                <Select
                  options={options}
                  value={selectedOption}
                  onChange={option => {
                    console.log(option);
                    console.error('TODO: Implement me');
                  }}
                />
              </div>
              <Button
                icon="settings"
                variant="ghost"
                onClick={() => {
                  setCurrentlyEditingScorerNdx(scorerNdx);
                }}
              />
              {/* <Button
            icon="copy"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          /> */}
              <Button
                icon="delete"
                variant="ghost"
                onClick={() => {
                  deleteScorer(scorerNdx);
                }}
              />
            </Row>
          );
        })}
        <Row>
          <Button
            icon="add-new"
            variant="ghost"
            onClick={() => {
              addScorer();
            }}
          />
        </Row>
        <ScorerDrawer
          entity={entity}
          project={project}
          open={currentlyEditingScorerNdx !== null}
          onClose={newScorerRef => {
            if (newScorerRef && currentlyEditingScorerNdx !== null) {
              editConfig(draft => {
                draft.evaluationDefinition.properties.scorers[
                  currentlyEditingScorerNdx
                ].originalSourceRef = newScorerRef;
              });
            }
            setCurrentlyEditingScorerNdx(null);
          }}
          initialScorerRef={
            currentlyEditingScorerNdx !== null
              ? scorers[currentlyEditingScorerNdx]?.originalSourceRef ??
                undefined
              : undefined
          }
        />
      </Column>
    </ConfigSection>
  );
};

const emptyScorer = (entity: string, project: string): ObjectVersionSchema => ({
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

const useScorer = clientBound(hookify(getScorerByRef));

const ScorerDrawer: React.FC<{
  entity: string;
  project: string;
  open: boolean;
  onClose: (newScorerRef?: string) => void;
  initialScorerRef?: string;
}> = ({entity, project, open, onClose, initialScorerRef}) => {
  const scorerFormRef = useRef<ScorerFormRef | null>(null);
  const onSave = useCallback(async () => {
    const newScorerRef = await scorerFormRef.current?.saveScorer();
    console.log('newScorerRef', newScorerRef);
    onClose(newScorerRef);
  }, [onClose]);

  const scorerQuery = useScorer(initialScorerRef);
  console.log('scorerQuery', scorerQuery);

  const scorerObj = useMemo(() => {
    if (initialScorerRef) {
      return scorerQuery.data ?? emptyScorer(entity, project);
    } else {
      return emptyScorer(entity, project);
    }
  }, [entity, initialScorerRef, project, scorerQuery.data]);

  if (scorerQuery.loading) {
    // TODO: Show a loading indicator
    return null;
  }

  if (scorerQuery.error) {
    // TODO: Show a loading indicator
    return null;
  }

  return (
    <ReusableDrawer
      open={open}
      onClose={() => onClose()}
      title="Scorer Configuration"
      onSave={onSave}>
      <Tailwind>
        <LLMAsAJudgeScorerForm
          key={initialScorerRef}
          ref={scorerFormRef}
          scorer={scorerObj}
          onValidationChange={() => {
            // Pass
          }}
        />
      </Tailwind>
    </ReusableDrawer>
  );
};

const ModelsConfigSection: React.FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  return (
    <ConfigSection title="Models" icon="model">
      <Column style={{gap: '8px'}}>
        <Row style={{alignItems: 'center', gap: '8px'}}>
          <div style={{flex: 1}}>
            <Select
              options={[]}
              value={''}
              onChange={option => {
                console.log(option);
                console.error('TODO: Implement me');
              }}
            />
          </div>
          <Button
            icon="settings"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          />
          <Button
            icon="copy"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          />
          <Button
            icon="remove"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          />
        </Row>
        <Row>
          <Button
            icon="add-new"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          />
        </Row>
      </Column>
    </ConfigSection>
  );
};
