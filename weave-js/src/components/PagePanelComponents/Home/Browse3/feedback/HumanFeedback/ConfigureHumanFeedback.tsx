import {Popover} from '@mui/material';
import {Switch} from '@wandb/weave/components';
import {Button} from '@wandb/weave/components/Button';
import {CodeEditor} from '@wandb/weave/components/CodeEditor';
import {
  DraggableGrow,
  DraggableHandle,
} from '@wandb/weave/components/DraggablePopups';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useEffect, useRef, useState} from 'react';

import {TraceObjCreateRes} from '../../pages/wfReactInterface/traceServerClientTypes';
import {tsHumanAnnotationColumn} from './humanFeedbackTypes';

type ConfigureHumanFeedbackProps = {
  columnVisibilityModel: Record<string, boolean>;
  setColumnVisibilityModel: (model: Record<string, boolean>) => void;
  columns: tsHumanAnnotationColumn[];
  onSaveColumn: (column: tsHumanAnnotationColumn) => Promise<TraceObjCreateRes>;
};

type EditingState = {
  isEditing: boolean;
  column: tsHumanAnnotationColumn | null;
  jsonSchema: string;
  error: string;
};

export const ConfigureHumanFeedback: React.FC<ConfigureHumanFeedbackProps> = ({
  columnVisibilityModel,
  setColumnVisibilityModel,
  columns,
  onSaveColumn,
}) => {
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<EditingState>({
    isEditing: false,
    column: null,
    jsonSchema: '',
    error: '',
  });
  const lowerSearch = search.toLowerCase();
  const filteredColumns = search
    ? columns.filter(col =>
        (col.name ?? '').toLowerCase().includes(lowerSearch)
      )
    : columns;

  const ref = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const onClickConfigure = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(anchorEl ? null : ref.current);
    setSearch('');
    setEditing({isEditing: false, column: null, jsonSchema: '', error: ''});
  };
  const open = Boolean(anchorEl);
  const id = open ? 'human-feedback-popper' : undefined;

  const toggleColumnVisibility = useCallback(
    (columnRef: string) => {
      setColumnVisibilityModel({
        ...columnVisibilityModel,
        [columnRef]: !columnVisibilityModel[columnRef],
      });
    },
    [columnVisibilityModel, setColumnVisibilityModel]
  );

  const handleEdit = (column: tsHumanAnnotationColumn) => {
    setEditing({isEditing: true, column, jsonSchema: '', error: ''});
  };
  const handleBack = () => {
    setEditing({isEditing: false, column: null, jsonSchema: '', error: ''});
  };
  const handleColumnSave = (updatedColumn: tsHumanAnnotationColumn) => {
    try {
      updatedColumn.json_schema = JSON.parse(editing.jsonSchema);
    } catch (e) {
      setEditing({...editing, error: `Invalid JSON schema: ${e}`});
      return;
    }
    onSaveColumn(updatedColumn);
    setEditing({isEditing: false, column: null, jsonSchema: '', error: ''});
  };

  useEffect(() => {
    if (editing.column) {
      setEditing(e => ({
        ...e,
        jsonSchema: JSON.stringify(e.column?.json_schema, null, 2),
      }));
    }
  }, [editing.column]);

  return (
    <>
      <span ref={ref}>
        <Button
          variant="ghost"
          icon="settings"
          tooltip="Configure Human Feedback"
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
                  !editing.isEditing ? 'bg-teal-300' : 'bg-moon-300'
                }`}
              />
              <div
                className={`h-0.5 w-12 ${
                  editing.isEditing ? 'bg-teal-300' : 'bg-moon-300'
                }`}
              />
            </div>

            {!editing.isEditing ? (
              <>
                <DraggableHandle>
                  <div className="flex items-center pb-8">
                    <div className="flex-auto text-xl font-semibold">
                      Configure human feedback
                    </div>
                  </div>
                </DraggableHandle>

                <div className="mb-8">
                  <TextField
                    placeholder="Filter columns"
                    autoFocus
                    value={search}
                    onChange={setSearch}
                  />
                </div>

                <div className="max-h-[300px] overflow-auto">
                  {filteredColumns.map(col => {
                    const idSwitch = `toggle-feedback_${col.ref}`;
                    return (
                      <div key={col.ref} className="flex items-center py-2">
                        <Switch.Root
                          id={idSwitch}
                          size="small"
                          checked={columnVisibilityModel[col.ref] ?? true}
                          onCheckedChange={() =>
                            toggleColumnVisibility(col.ref)
                          }>
                          <Switch.Thumb
                            size="small"
                            checked={columnVisibilityModel[col.ref] ?? true}
                          />
                        </Switch.Root>
                        <label
                          htmlFor={idSwitch}
                          className="ml-6 flex-grow cursor-pointer">
                          {col.name}
                        </label>
                        <Button
                          variant="quiet"
                          size="small"
                          icon="pencil-edit"
                          onClick={() => handleEdit(col)}
                        />
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <>
                <DraggableHandle>
                  <div className="flex items-center pb-8">
                    <Button
                      variant="ghost"
                      size="small"
                      icon="chevron-back"
                      onClick={handleBack}
                      className="mr-4"
                    />
                    <div className="flex-auto text-xl font-semibold">
                      Edit column
                    </div>
                  </div>
                </DraggableHandle>

                <div>
                  <div className="mb-8">
                    <label className="mb-1 block text-sm font-semibold">
                      Name
                    </label>
                    <TextField
                      value={editing.column?.name ?? ''}
                      onChange={value => {
                        if (editing.column) {
                          setEditing({
                            ...editing,
                            column: {...editing.column, name: value},
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
                      value={editing.column?.description ?? ''}
                      onChange={value => {
                        if (editing.column) {
                          setEditing({
                            ...editing,
                            column: {...editing.column, description: value},
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
                      value={editing.jsonSchema}
                      onChange={value =>
                        setEditing({...editing, jsonSchema: value})
                      }
                    />
                    {editing.error && (
                      <div className="mt-1 text-sm text-red-500">
                        {editing.error}
                      </div>
                    )}
                  </div>

                  <div className="mt-8 flex justify-start p-2">
                    <Button
                      size="medium"
                      variant="primary"
                      onClick={() =>
                        editing.column && handleColumnSave(editing.column)
                      }>
                      Save
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        </Tailwind>
      </Popover>
    </>
  );
};
