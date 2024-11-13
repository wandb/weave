import {toast} from '@wandb/weave/common/components/elements/Toast';
import {Button} from '@wandb/weave/components/Button';
import {DraggableHandle} from '@wandb/weave/components/DraggablePopups';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {parseRef} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useEffect, useMemo, useState} from 'react';

import {useCreateBaseObjectInstance} from '../../pages/wfReactInterface/baseObjectClassQuery';
import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {sanitizeObjectId} from '../../pages/wfReactInterface/traceServerDirectClient';
import {projectIdFromParts} from '../../pages/wfReactInterface/tsDataModelHooks';
import {NumericalTextField} from './HumanFeedback';
import {FeedbackSchemaType, tsHumanAnnotationSpec} from './humanFeedbackTypes';

type EditOrCreateAnnotationSpecProps = {
  entityName: string;
  projectName: string;
  spec?: AnnotationSpec;
  onSaveCB?: () => void;
  onBackButtonClick?: () => void;
};

type EditingState = {
  spec: AnnotationSpec | null;
  error: string;
};

export const EditOrCreateAnnotationSpec: React.FC<
  EditOrCreateAnnotationSpecProps
> = ({entityName, projectName, spec, onSaveCB, onBackButtonClick}) => {
  const createHumanFeedback = useCreateBaseObjectInstance('AnnotationSpec');
  const [editState, setEditState] = useState<EditingState>({
    spec: spec ?? {},
    error: '',
  });
  const action = spec === undefined ? 'Create' : 'Edit';
  const specType: FeedbackSchemaType | undefined =
    editState.spec?.json_schema?.type;

  const allRequiredFieldsFilled =
    editState.spec?.name != null && specType != null;
  const dirty = useMemo(() => {
    return !_.isEqual(editState.spec, spec);
  }, [editState.spec, spec]);

  const handleSave = (updatedSpec: AnnotationSpec) => {
    try {
      objectIdFromSpec(updatedSpec);
    } catch (e) {
      setEditState(e => ({
        ...e,
        error: `Invalid object name: '${updatedSpec.name}'`,
      }));
      return;
    }

    createHumanFeedback({
      obj: {
        project_id: projectIdFromParts({
          entity: entityName,
          project: projectName,
        }),
        object_id: objectIdFromSpec(updatedSpec),
        val: updatedSpec,
      },
    })
      .then(res => {
        if ('reason' in res) {
          // actually an error
          console.error(res);
          setEditState({
            ...editState,
            error: JSON.stringify(res),
          });
          return;
        }
        toast(
          `Saved annotation spec: ${sanitizeObjectId(updatedSpec.name ?? '')}`,
          {type: 'success'}
        );
        onSaveCB?.();
      })
      .catch(e => {
        setEditState({
          ...editState,
          error: e.toString(),
        });
      });
  };

  return (
    <>
      {onBackButtonClick && (
        <DraggableHandle>
          <div className="flex items-center pb-8">
            <Button
              variant="ghost"
              size="small"
              icon="chevron-back"
              onClick={onBackButtonClick}
              className="mr-4"
            />
            <div className="flex-auto text-xl font-semibold">
              {action} annotation
            </div>
          </div>
        </DraggableHandle>
      )}

      <div>
        <div className="mb-8">
          <label className="mb-1 block text-sm font-semibold">Name</label>
          <TextField
            value={editState.spec?.name ?? ''}
            disabled={action === 'Edit'}
            onChange={value => {
              if (!editState.spec) {
                return;
              }
              if (value === '') {
                setEditState({
                  ...editState,
                  spec: {...editState.spec, name: null},
                });
                return;
              }
              setEditState({
                ...editState,
                spec: {...editState.spec, name: value},
              });
            }}
          />
        </div>

        <div className="mb-8">
          <label className="mb-1 block text-sm font-semibold">
            Description
          </label>
          <TextField
            value={editState.spec?.description ?? ''}
            onChange={value => {
              if (editState.spec) {
                setEditState({
                  ...editState,
                  spec: {...editState.spec, description: value},
                });
              }
            }}
          />
        </div>

        <TypeSelector
          value={editState.spec?.json_schema?.type}
          onChange={value => {
            setEditState({
              ...editState,
              spec: {
                ...editState.spec,
                json_schema: {
                  ...editState.spec?.json_schema,
                  type: value,
                },
              },
            });
          }}
          disabled={action === 'Edit'}
        />

        {specType === 'number' && (
          <div className="mb-8 mt-8">
            <label className="mb-1 block text-sm font-semibold">
              Minimum value (optional)
            </label>
            <NumericalTextField
              value={editState.spec?.json_schema?.min}
              onChange={value => {
                setEditState({
                  ...editState,
                  spec: {
                    ...editState.spec,
                    json_schema: {...editState.spec?.json_schema, min: value},
                  },
                });
              }}
            />
            <label className="mb-1 mt-4 block text-sm font-semibold">
              Maximum value (optional)
            </label>
            <NumericalTextField
              value={editState.spec?.json_schema?.max}
              onChange={value => {
                setEditState({
                  ...editState,
                  spec: {
                    ...editState.spec,
                    json_schema: {...editState.spec?.json_schema, max: value},
                  },
                });
              }}
            />
          </div>
        )}

        {specType === 'array' && (
          <CategoricalOptions
            editState={editState}
            setEditState={setEditState}
          />
        )}

        {specType === 'string' && (
          <div className="mb-8 mt-8">
            <label className="mb-1 block text-sm font-semibold">
              Max length (optional)
            </label>
            <NumericalTextField
              value={editState.spec?.json_schema?.max_length}
              onChange={value => {
                setEditState({
                  ...editState,
                  spec: {
                    ...editState.spec,
                    json_schema: {
                      ...editState.spec?.json_schema,
                      max_length: value,
                    },
                  },
                });
              }}
            />
          </div>
        )}

        {editState.error && (
          <div className="mt-1 text-sm text-red-500">
            Error: {editState.error}
          </div>
        )}

        <div className="mt-12 flex w-full">
          <Button
            size="medium"
            variant="primary"
            className="w-full"
            disabled={!allRequiredFieldsFilled || (action === 'Edit' && !dirty)}
            onClick={() => editState.spec && handleSave(editState.spec)}>
            Save
          </Button>
        </div>
      </div>
    </>
  );
};

type SchemaTypeOption = {
  label: string;
  value: FeedbackSchemaType;
};

const TypeSelector: React.FC<{
  value: FeedbackSchemaType;
  onChange: (value: FeedbackSchemaType) => void;
  disabled?: boolean;
}> = ({value, onChange, disabled}) => {
  const options: SchemaTypeOption[] = [
    {label: 'String', value: 'string'},
    {label: 'Number', value: 'number'},
    {label: 'Boolean', value: 'boolean'},
    {label: 'Categorical', value: 'array'},
  ];

  const optionValue = options.find(o => o.value === value);

  return (
    <div>
      <label className="mb-1 block text-sm font-semibold">Type</label>
      <Select<SchemaTypeOption>
        value={optionValue}
        options={options}
        isDisabled={disabled}
        onChange={(o: SchemaTypeOption | null) => {
          onChange(o?.value ?? options[0].value);
        }}
      />
    </div>
  );
};

const CategoricalOptions: React.FC<{
  editState: EditingState;
  setEditState: React.Dispatch<React.SetStateAction<EditingState>>;
}> = ({editState, setEditState}) => {
  const [options, setOptions] = useState<string[]>(
    editState.spec?.json_schema?.options ?? []
  );

  useEffect(() => {
    setEditState(state => ({
      ...state,
      spec: {...state.spec, json_schema: {...state.spec?.json_schema, options}},
    }));
  }, [options, setEditState]);

  return (
    <div className="mb-8 mt-8">
      <div className="mb-2 flex items-center">
        <label className="mb-1 block text-sm font-semibold">Options</label>
        <div className="text-gray-500 mb-1 ml-6 text-sm">{options.length}</div>
      </div>
      {options.map((option, i) => (
        <div key={i} className="mt-4 flex items-center">
          <TextField
            value={option}
            onChange={value => {
              setOptions(
                options
                  .slice(0, i)
                  .concat([value])
                  .concat(options.slice(i + 1))
              );
            }}
          />
          <Button
            size="medium"
            variant="ghost"
            icon="delete"
            className="ml-4"
            onClick={() => {
              setOptions(options.slice(0, i).concat(options.slice(i + 1)));
            }}
          />
        </div>
      ))}
      <Button
        size="small"
        variant="secondary"
        icon="add-new"
        className="mt-8 w-full p-8"
        onClick={() => setOptions([...options, ''])}>
        Add new option
      </Button>
    </div>
  );
};

const objectIdFromSpec = (spec: tsHumanAnnotationSpec | AnnotationSpec) => {
  if ('ref' in spec) {
    return parseRef(spec.ref).artifactName;
  }
  if (spec.name == null) {
    throw new Error('No ref or name provided for annotation spec');
  }
  return sanitizeObjectId(spec.name);
};
