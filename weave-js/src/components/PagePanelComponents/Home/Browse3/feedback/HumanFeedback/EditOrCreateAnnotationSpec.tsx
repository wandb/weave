import {toast} from '@wandb/weave/common/components/elements/Toast';
import {Button} from '@wandb/weave/components/Button';
import {CodeEditor} from '@wandb/weave/components/CodeEditor';
import {DraggableHandle} from '@wandb/weave/components/DraggablePopups';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {parseRef} from '@wandb/weave/react';
import React, {useEffect, useState} from 'react';

import {useCreateBaseObjectInstance} from '../../pages/wfReactInterface/baseObjectClassQuery';
import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {sanitizeObjectId} from '../../pages/wfReactInterface/traceServerDirectClient';
import {projectIdFromParts} from '../../pages/wfReactInterface/tsDataModelHooks';
import {tsHumanAnnotationSpec} from './humanFeedbackTypes';

type EditOrCreateAnnotationSpecProps = {
  entityName: string;
  projectName: string;
  spec?: AnnotationSpec;
  onSaveCB?: () => void;
  onBackButtonClick?: () => void;
};

type EditingState = {
  spec: AnnotationSpec | null;
  jsonSchema: string;
  error: string;
};

export const EditOrCreateAnnotationSpec: React.FC<
  EditOrCreateAnnotationSpecProps
> = ({entityName, projectName, spec, onSaveCB, onBackButtonClick}) => {
  const createHumanFeedback = useCreateBaseObjectInstance('AnnotationSpec');
  const [editState, setEditState] = useState<EditingState>({
    spec: spec ?? {},
    jsonSchema: JSON.stringify(spec?.json_schema ?? {}, null, 2),
    error: '',
  });
  const action = spec === undefined ? 'Create' : 'Edit';

  const handleColumnSave = (updatedSpec: AnnotationSpec) => {
    try {
      updatedSpec.json_schema = JSON.parse(editState.jsonSchema);
    } catch (e) {
      setEditState({...editState, error: `Invalid JSON schema: ${e}`});
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
      .then(() => {
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

  useEffect(() => {
    if (editState.spec) {
      setEditState(e => ({
        ...e,
        jsonSchema: JSON.stringify(e.spec?.json_schema, null, 2),
      }));
    }
  }, [editState.spec, setEditState]);

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
              if (editState.spec) {
                setEditState({
                  ...editState,
                  spec: {...editState.spec, name: value},
                });
              }
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

        <div className="my-8">
          <label className="mb-1 block text-sm font-semibold">
            Json schema
          </label>
          <CodeEditor
            language="json"
            value={editState.jsonSchema}
            onChange={value => setEditState({...editState, jsonSchema: value})}
          />
          {editState.error && (
            <div className="mt-1 text-sm text-red-500">{editState.error}</div>
          )}
        </div>

        <div className="mt-8 flex justify-start p-2">
          <Button
            size="medium"
            variant="primary"
            onClick={() => editState.spec && handleColumnSave(editState.spec)}>
            Save
          </Button>
        </div>
      </div>
    </>
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
