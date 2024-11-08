import {Switch} from '@wandb/weave/components';
import {Button} from '@wandb/weave/components/Button';
import {DraggableHandle} from '@wandb/weave/components/DraggablePopups';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useCallback, useState} from 'react';

import {tsHumanAnnotationSpec} from './humanFeedbackTypes';

type ToggleColumnVisibilityProps = {
  columns: tsHumanAnnotationSpec[];
  columnVisibilityModel: Record<string, boolean>;
  setColumnVisibilityModel: (model: Record<string, boolean>) => void;
  onEdit: (column: tsHumanAnnotationSpec) => void;
};

export const ToggleColumnVisibility: React.FC<ToggleColumnVisibilityProps> = ({
  columns,
  columnVisibilityModel,
  setColumnVisibilityModel,
  onEdit,
}) => {
  const [search, setSearch] = useState('');
  const lowerSearch = search.toLowerCase();
  const filteredColumns = search
    ? columns.filter(col =>
        (col.name ?? '').toLowerCase().includes(lowerSearch)
      )
    : columns;

  const toggleColumnVisibility = useCallback(
    (columnRef: string) => {
      setColumnVisibilityModel({
        ...columnVisibilityModel,
        [columnRef]: !columnVisibilityModel[columnRef],
      });
    },
    [columnVisibilityModel, setColumnVisibilityModel]
  );

  return (
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
                onCheckedChange={() => toggleColumnVisibility(col.ref)}>
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
                onClick={() => onEdit(col)}
              />
            </div>
          );
        })}
      </div>
    </>
  );
};
