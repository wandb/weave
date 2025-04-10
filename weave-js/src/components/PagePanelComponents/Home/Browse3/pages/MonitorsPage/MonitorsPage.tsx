import {Box, Switch} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';
import {IconNames} from '@wandb/weave/components/Icon';
import {FilterableObjectVersionsTable} from '../ObjectsPage/ObjectVersionsTable';
import {CellValueBoolean} from '../../../Browse2/CellValueBoolean';
export const MonitorsPage = ({
  entity,
  project,
}: {
  entity: string;
  project: string;
}) => {
  return (
    <Tailwind>
      <Box>
        <Box className="mx-16 my-16 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Monitors</h1>
          <Button variant="primary" size="large" startIcon={IconNames.AddNew}>
            Create monitor
          </Button>
        </Box>
        <FilterableObjectVersionsTable
          entity={entity}
          project={project}
          objectTitle="Monitor"
          hideCategoryColumn
          frozenFilter={{
            baseObjectClass: 'Monitor',
          }}
          metadataOnly={false}
          customColumns={[
            {
              field: 'description',
              headerName: 'Description',
              flex: 1,
              valueGetter: (_, row) => {
                return row.obj.val['description'];
              },
            },
            {
              field: 'active',
              headerName: 'Active',
              valueGetter: (_, row) => {
                return row.obj.val['active'];
              },
              renderCell: params => {
                return <CellValueBoolean value={params.value} />;
              },
            },
          ]}
        />
      </Box>
    </Tailwind>
  );
};
