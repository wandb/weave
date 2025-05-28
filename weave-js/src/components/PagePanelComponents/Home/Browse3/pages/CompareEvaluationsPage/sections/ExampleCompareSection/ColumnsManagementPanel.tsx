import {
  GridApi,
  GridColumnGroup,
  GridColumnLookup,
  gridColumnLookupSelector,
  GridColumnsPanel,
  GridColumnsPanelProps,
  GridColumnVisibilityModel,
  gridColumnVisibilityModelSelector,
  isLeaf,
  useGridApiContext,
  useGridRootProps,
  useGridSelector,
} from '@mui/x-data-grid-pro';
import {Checkbox} from '@wandb/weave/components/Checkbox';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {FC, useMemo} from 'react';

const getColumnGroupLeaves = (
  group: GridColumnGroup,
  callback: (field: string) => void
) => {
  group.children.forEach(child => {
    if (isLeaf(child)) {
      callback(child.field);
    } else {
      getColumnGroupLeaves(child, callback);
    }
  });
};

const ColumnGroup: FC<{
  group: GridColumnGroup;
  columnLookup: GridColumnLookup;
  apiRef: React.RefObject<GridApi>;
  columnVisibilityModel: GridColumnVisibilityModel;
}> = ({group, columnLookup, apiRef, columnVisibilityModel}) => {
  const leaves = React.useMemo(() => {
    const fields: string[] = [];
    getColumnGroupLeaves(group, field => fields.push(field));
    return fields;
  }, [group]);

  const {isGroupChecked, isGroupIndeterminate} = React.useMemo(() => {
    return {
      isGroupChecked: leaves.every(
        field => columnVisibilityModel[field] !== false
      ),
      isGroupIndeterminate:
        leaves.some(field => columnVisibilityModel[field] === false) &&
        !leaves.every(field => columnVisibilityModel[field] === false),
    };
  }, [columnVisibilityModel, leaves]);

  const toggleColumnGroup = (checked: boolean) => {
    const newColumnVisibilityModel = {
      ...columnVisibilityModel,
    };
    getColumnGroupLeaves(group, field => {
      newColumnVisibilityModel[field] = checked;
    });
    apiRef.current?.setColumnVisibilityModel(newColumnVisibilityModel);
  };

  const toggleColumn = (field: string, checked: boolean) => {
    apiRef.current?.setColumnVisibility(field, checked);
  };

  const groupControlsChildrenVisibility = useMemo(() => {
    return !!(group as any)[CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY];
  }, [group]);

  const idCheckboxGroup = `toggle-group-vis_${group.groupId}`;

  return (
    <div className="mb-2">
      <div className="flex items-center py-2">
        <Checkbox
          id={idCheckboxGroup}
          size="small"
          checked={isGroupIndeterminate ? 'indeterminate' : isGroupChecked}
          onCheckedChange={toggleColumnGroup}
        />
        <label htmlFor={idCheckboxGroup} className="ml-4 cursor-pointer">
          {group.headerName ?? group.groupId}
        </label>
      </div>
      {!groupControlsChildrenVisibility && (
        <div className="ml-18">
          {group.children.map(child => {
            if (isLeaf(child)) {
              const idCheckbox = `toggle-vis_${child.field}`;
              const checked = columnVisibilityModel[child.field] !== false;
              const label = columnLookup[child.field].headerName ?? child.field;

              return (
                <div key={child.field} className="flex items-center py-2">
                  <Checkbox
                    id={idCheckbox}
                    size="small"
                    checked={checked}
                    onCheckedChange={() => toggleColumn(child.field, !checked)}
                  />
                  <label htmlFor={idCheckbox} className="ml-4 cursor-pointer">
                    {label}
                  </label>
                </div>
              );
            } else {
              return (
                <ColumnGroup
                  group={child}
                  columnLookup={columnLookup}
                  key={child.groupId}
                  apiRef={apiRef}
                  columnVisibilityModel={columnVisibilityModel}
                />
              );
            }
          })}
        </div>
      )}
    </div>
  );
};

export const CUSTOM_GROUP_KEY_TO_CONTROL_CHILDREN_VISIBILITY =
  'controlsChildrenVisibility';

export const ColumnsManagementPanel: FC<GridColumnsPanelProps> = props => {
  const apiRef = useGridApiContext();
  const rootProps = useGridRootProps();
  const columnLookup = useGridSelector(apiRef, gridColumnLookupSelector);
  const columnVisibilityModel = useGridSelector(
    apiRef,
    gridColumnVisibilityModelSelector
  );

  const columnGroupingModel = rootProps.columnGroupingModel;

  if (!columnGroupingModel) {
    return <GridColumnsPanel {...props} />;
  }

  return (
    <Tailwind>
      <div
        className="min-w-[360px] p-12"
        style={{fontFamily: 'Source Sans Pro', fontSize: '14px'}}>
        <div className="mb-4 font-semibold">Manage columns</div>
        <div>
          {columnGroupingModel.map(group => (
            <ColumnGroup
              group={group}
              columnLookup={columnLookup}
              columnVisibilityModel={columnVisibilityModel}
              key={group.groupId}
              apiRef={apiRef}
            />
          ))}
        </div>
      </div>
    </Tailwind>
  );
};
