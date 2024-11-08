import {Popover} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {DraggableGrow} from '@wandb/weave/components/DraggablePopups';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState} from 'react';

import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {TraceObjCreateRes} from '../../pages/wfReactInterface/traceServerClientTypes';
import {EditAnnotationSpec} from './EditAnnotationSpec';
import {tsHumanAnnotationSpec} from './humanFeedbackTypes';
import {ToggleColumnVisibility} from './ToggleColumnVisibility';

type ManageHumanFeedbackProps = {
  columnVisibilityModel: Record<string, boolean>;
  setColumnVisibilityModel: (model: Record<string, boolean>) => void;
  specs: tsHumanAnnotationSpec[];
  onSaveSpec: (
    spec: tsHumanAnnotationSpec | AnnotationSpec
  ) => Promise<TraceObjCreateRes>;
};

export type EditingState = {
  isEditing: boolean;
  spec: tsHumanAnnotationSpec | AnnotationSpec | null;
  jsonSchema: string;
  error: string;
};

export const ManageHumanFeedback: React.FC<ManageHumanFeedbackProps> = ({
  columnVisibilityModel,
  setColumnVisibilityModel,
  specs,
  onSaveSpec,
}) => {
  const [editState, setEditState] = useState<EditingState>({
    isEditing: false,
    spec: null,
    jsonSchema: '',
    error: '',
  });
  const ref = React.useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const onClickConfigure = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
    setEditState({isEditing: false, spec: null, jsonSchema: '', error: ''});
  };

  const handleBack = () => {
    setEditState({isEditing: false, spec: null, jsonSchema: '', error: ''});
  };

  const open = Boolean(anchorEl);
  const id = open ? 'human-feedback-popper' : undefined;

  return (
    <>
      <span ref={ref}>
        <Button
          variant="ghost"
          icon="settings"
          tooltip="Configure human feedback"
          onClick={onClickConfigure}
        />
      </span>
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'center',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'center',
        }}
        slotProps={{
          paper: {
            sx: {
              overflow: 'visible',
            },
          },
        }}
        onClose={() => setAnchorEl(null)}
        TransitionComponent={DraggableGrow}>
        <Tailwind>
          <div className="min-w-[360px] p-12">
            <div className="mb-4 flex gap-2">
              <div
                className={`h-0.5 w-12 ${
                  editState.isEditing ? 'bg-teal-300' : 'bg-moon-300'
                }`}
              />
            </div>

            {editState.isEditing ? (
              <EditAnnotationSpec
                editState={editState}
                setEditState={setEditState}
                onSave={onSaveSpec}
                onBackButtonClick={handleBack}
              />
            ) : (
              <ToggleColumnVisibility
                columns={specs}
                columnVisibilityModel={columnVisibilityModel}
                setColumnVisibilityModel={setColumnVisibilityModel}
                onEdit={spec =>
                  setEditState({
                    isEditing: true,
                    spec,
                    jsonSchema: '',
                    error: '',
                  })
                }
              />
            )}
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};
