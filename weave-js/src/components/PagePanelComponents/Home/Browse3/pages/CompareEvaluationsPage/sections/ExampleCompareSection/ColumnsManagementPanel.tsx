import {Box, Checkbox, FormControlLabel, Stack} from '@mui/material';
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

  return (
    <div>
      <FormControlLabel
        control={
          <Checkbox
            checked={isGroupChecked}
            indeterminate={isGroupIndeterminate}
            size="small"
            sx={{p: 1}}
          />
        }
        label={group.headerName ?? group.groupId}
        onChange={(_, newValue) => toggleColumnGroup(newValue)}
      />
      {!groupControlsChildrenVisibility && (
        <Box sx={{pl: 3.5}}>
          {group.children.map(child => {
            return isLeaf(child) ? (
              <Stack direction="row" key={child.field}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={columnVisibilityModel[child.field] !== false}
                      size="small"
                      sx={{p: 1}}
                    />
                  }
                  label={columnLookup[child.field].headerName ?? child.field}
                  onChange={(_, newValue) =>
                    toggleColumn(child.field, newValue)
                  }
                />
              </Stack>
            ) : (
              <ColumnGroup
                group={child}
                columnLookup={columnLookup}
                key={child.groupId}
                apiRef={apiRef}
                columnVisibilityModel={columnVisibilityModel}
              />
            );
          })}
        </Box>
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
    <Box sx={{px: 2, py: 0.5}}>
      {columnGroupingModel.map(group => (
        <ColumnGroup
          group={group}
          columnLookup={columnLookup}
          columnVisibilityModel={columnVisibilityModel}
          key={group.groupId}
          apiRef={apiRef}
        />
      ))}
    </Box>
  );
};
