import {toast} from '@wandb/weave/common/components/elements/Toast';
import {Button} from '@wandb/weave/components/Button';
import {CodeEditor} from '@wandb/weave/components/CodeEditor';
import {DraggableHandle} from '@wandb/weave/components/DraggablePopups';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useEffect} from 'react';

import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {TraceObjCreateRes} from '../../pages/wfReactInterface/traceServerClientTypes';
import {tsHumanAnnotationSpec} from './humanFeedbackTypes';
import {EditingState} from './ManageHumanFeedback';

type EditAnnotationSpecProps = {
  editState: EditingState;
  setEditState: React.Dispatch<React.SetStateAction<EditingState>>;
  onSave: (
    spec: tsHumanAnnotationSpec | AnnotationSpec
  ) => Promise<TraceObjCreateRes>;
  onBackButtonClick?: () => void;
};

export const EditAnnotationSpec: React.FC<EditAnnotationSpecProps> = ({
  editState,
  setEditState,
  onSave,
  onBackButtonClick,
}) => {
  const handleColumnSave = (updatedSpec: AnnotationSpec) => {
    try {
      updatedSpec.json_schema = JSON.parse(editState.jsonSchema);
    } catch (e) {
      setEditState({...editState, error: `Invalid JSON schema: ${e}`});
      return;
    }
    onSave(updatedSpec)
      .then(() => {
        setEditState({isEditing: false, spec: null, jsonSchema: '', error: ''});
        toast('Saved column', {type: 'success'});
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
            <div className="flex-auto text-xl font-semibold">Edit column</div>
          </div>
        </DraggableHandle>
      )}

      <div>
        <div className="mb-8">
          <label className="mb-1 block text-sm font-semibold">Name</label>
          <TextField
            value={editState.spec?.name ?? ''}
            disabled={true}
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
