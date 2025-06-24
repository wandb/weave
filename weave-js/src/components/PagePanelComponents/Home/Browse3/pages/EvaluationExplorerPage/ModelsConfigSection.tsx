import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useMemo, useRef, useState} from 'react';

import {ReusableDrawer} from '../../ReusableDrawer';
import {refStringToName} from './common';
import {LoadingSelect} from './components';
import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {Column, ConfigSection, Row} from './layout';
import {getLatestModelRefs} from './query';

// Default option for creating a new model from scratch
const newModelOption = {
  label: 'New Model',
  value: 'new-model',
};

// Create the hook for fetching model refs
// This wraps the async query function in a React hook that manages loading/error states
const useLatestModelRefs = clientBound(hookify(getLatestModelRefs));

/**
 * Configuration section for managing models in the evaluation.
 * Allows users to add, edit, and remove models that will be evaluated.
 */
export const ModelsConfigSection: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const modelRefsQuery = useLatestModelRefs(entity, project);

  const [currentlyEditingModelNdx, setCurrentlyEditingModelNdx] = useState<
    number | null
  >(null);

  const models = useMemo(() => {
    return config.models;
  }, [config]);

  const addModel = useCallback(() => {
    editConfig(draft => {
      draft.models.push({
        originalSourceRef: null,
        dirtied: false,
        properties: {
          name: '',
          description: '',
          systemPromptTemplate: '',
          modelPromptTemplate: '',
          outputSchema: {
            type: 'object',
            properties: {},
          },
        },
      });
    });
  }, [editConfig]);

  const modelOptions = useMemo(() => {
    return [
      {
        label: 'Create new model',
        options: [newModelOption],
      },
      {
        label: 'Load existing model',
        options:
          modelRefsQuery.data?.map(ref => ({
            label: refStringToName(ref),
            value: ref,
          })) ?? [],
      },
    ];
  }, [modelRefsQuery.data]);

  const deleteModel = useCallback(
    (modelNdx: number) => {
      editConfig(draft => {
        draft.models.splice(modelNdx, 1);
      });
    },
    [editConfig]
  );

  const updateModelRef = useCallback(
    (modelNdx: number, ref: string | null) => {
      editConfig(draft => {
        if (ref === 'new-model' || ref === null) {
          // Reset to empty model
          draft.models[modelNdx].originalSourceRef = null;
          draft.models[modelNdx].dirtied = false;
        } else {
          // Set the selected model ref
          draft.models[modelNdx].originalSourceRef = ref;
          draft.models[modelNdx].dirtied = false;
        }
      });
    },
    [editConfig]
  );

  return (
    <ConfigSection
      title="Models"
      icon="model"
      style={{
        paddingBottom: '0px',
        paddingRight: '0px',
      }}>
      <Column style={{gap: '8px'}}>
        {models.map((model, modelNdx) => {
          let selectedOption = newModelOption;
          const options = [...modelOptions];
          if (model.originalSourceRef) {
            const name = refStringToName(model.originalSourceRef);
            selectedOption = {
              label: name,
              value: model.originalSourceRef,
            };
            // Add current selection if it's not in the list (e.g., from another project)
            const allOptions = options.flatMap(group => group.options);
            if (!allOptions.find(opt => opt.value === model.originalSourceRef)) {
              // Add to the existing models group
              options[1].options.unshift(selectedOption);
            }
          }
          
          // Show loading state for individual dropdowns if query is loading
          if (modelRefsQuery.loading) {
            return (
              <Row key={modelNdx} style={{alignItems: 'center', gap: '8px'}}>
                <div style={{flex: 1}}>
                  <LoadingSelect />
                </div>
                <Button icon="settings" variant="ghost" disabled />
                <Button icon="delete" variant="ghost" disabled />
              </Row>
            );
          }
          
          return (
            <Row key={modelNdx} style={{alignItems: 'center', gap: '8px'}}>
              <div style={{flex: 1}}>
                <Select
                  options={options}
                  value={selectedOption}
                  onChange={option => {
                    updateModelRef(modelNdx, option?.value ?? null);
                  }}
                />
              </div>
              <Button
                icon="settings"
                variant="ghost"
                onClick={() => {
                  setCurrentlyEditingModelNdx(modelNdx);
                }}
              />
              {/* TODO: Implement copy functionality
              <Button
                icon="copy"
                variant="ghost"
                onClick={() => {
                  console.error('TODO: Implement copy model');
                }}
              /> */}
              <Button
                icon="delete"
                variant="ghost"
                onClick={() => {
                  deleteModel(modelNdx);
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
              addModel();
            }}
          />
        </Row>
        <ModelDrawer
          entity={entity}
          project={project}
          open={currentlyEditingModelNdx !== null}
          onClose={newModelRef => {
            if (newModelRef && currentlyEditingModelNdx !== null) {
              editConfig(draft => {
                // Update the model with the new reference
                draft.models[currentlyEditingModelNdx].originalSourceRef =
                  newModelRef;
                // Mark as not dirtied since it's now saved
                draft.models[currentlyEditingModelNdx].dirtied = false;
              });
            }
            setCurrentlyEditingModelNdx(null);
          }}
          initialModel={
            currentlyEditingModelNdx !== null
              ? models[currentlyEditingModelNdx]
              : undefined
          }
        />
      </Column>
    </ConfigSection>
  );
};

/**
 * Drawer component for configuring model details.
 * Provides a form interface for editing model properties like name, prompts, and output schema.
 *
 * @param entity - The Weave entity (organization/user)
 * @param project - The Weave project
 * @param open - Whether the drawer is open
 * @param onClose - Callback when drawer closes, receives new model ref if saved
 * @param initialModel - Existing model data to edit (optional)
 */
const ModelDrawer: React.FC<{
  entity: string;
  project: string;
  open: boolean;
  onClose: (newModelRef?: string) => void;
  initialModel?: {
    originalSourceRef: string | null;
    dirtied: boolean;
    properties: {
      name: string;
      description: string;
      systemPromptTemplate: string;
      modelPromptTemplate: string;
      outputSchema: any;
    };
  };
}> = ({entity, project, open, onClose, initialModel}) => {
  // TODO: Implement save functionality
  const onSave = useCallback(async () => {
    // TODO: Save model and get reference
    console.error('TODO: Implement model save');
    onClose();
  }, [onClose]);

  return (
    <ReusableDrawer
      open={open}
      onClose={() => onClose()}
      title="Model Configuration"
      onSave={onSave}>
      <Tailwind>
        <div className="p-4">
          {/* TODO: Add model configuration form components */}
          <p className="text-gray-500">
            Model configuration form will be implemented here
          </p>
        </div>
      </Tailwind>
    </ReusableDrawer>
  );
};
