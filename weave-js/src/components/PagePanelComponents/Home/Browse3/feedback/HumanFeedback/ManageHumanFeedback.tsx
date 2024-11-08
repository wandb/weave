import {Popover} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {DraggableGrow} from '@wandb/weave/components/DraggablePopups';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState} from 'react';

import {AnnotationSpec} from '../../pages/wfReactInterface/generatedBaseObjectClasses.zod';
import {EditOrCreateAnnotationSpec} from './EditOrCreateAnnotationSpec';
import {tsHumanAnnotationSpec} from './humanFeedbackTypes';
import {ToggleColumnVisibility} from './ToggleColumnVisibility';

type ManageHumanFeedbackProps = {
  entityName: string;
  projectName: string;
  columnVisibilityModel: Record<string, boolean>;
  setColumnVisibilityModel: (model: Record<string, boolean>) => void;
  specs: tsHumanAnnotationSpec[];
};

export const ManageHumanFeedback: React.FC<ManageHumanFeedbackProps> = ({
  entityName,
  projectName,
  columnVisibilityModel,
  setColumnVisibilityModel,
  specs,
}) => {
  const [editingSpec, setEditingSpec] = useState<
    tsHumanAnnotationSpec | AnnotationSpec | null
  >(null);
  const ref = React.useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const onClickConfigure = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
    setEditingSpec(null);
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
                  editingSpec ? 'bg-teal-300' : 'bg-moon-300'
                }`}
              />
            </div>

            {editingSpec ? (
              <EditOrCreateAnnotationSpec
                entityName={entityName}
                projectName={projectName}
                onSaveCB={() => setEditingSpec(null)}
                onBackButtonClick={() => setEditingSpec(null)}
                spec={editingSpec}
              />
            ) : (
              <ToggleColumnVisibility
                columns={specs}
                columnVisibilityModel={columnVisibilityModel}
                setColumnVisibilityModel={setColumnVisibilityModel}
                onEdit={setEditingSpec}
              />
            )}
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};
