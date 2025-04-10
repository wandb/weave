import {Box, Switch} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';
import {IconNames} from '@wandb/weave/components/Icon';
import {FilterableObjectVersionsTable} from '../ObjectsPage/ObjectVersionsTable';
import {CellValueBoolean} from '../../../Browse2/CellValueBoolean';
import {SmallRef} from '../../smallRef/SmallRef';
import {parseRef} from '../../../../../../react';
import {CellValue} from '../../../Browse2/CellValue';

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
              valueGetter: (_, row) => row.obj.val['description'],
              renderCell: params => <CellValue value={params.value} />,
            },
            {
              field: 'samplingRate',
              headerName: 'Sampling rate',
              width: 120,
              valueGetter: (_, row) => row.obj.val['sampling_rate'],
              renderCell: params => (
                <CellValue value={`${params.value * 100}%`} />
              ),
            },
            {
              field: 'ops',
              headerName: 'Ops',
              flex: 1,
              valueGetter: (_, row) => row.obj.val['call_filter.op_names'],
              renderCell: params => {
                const opRefs: string[] = params.value;
                return opRefs.length > 0 ? (
                  <div className="flex items-center gap-2">
                    <CellValue value={opRefs[0]} />
                    {opRefs.length > 1 ? (
                      <span>{`+${opRefs.length - 1}`}</span>
                    ) : null}
                  </div>
                ) : null;
              },
            },
            {
              field: 'scorers',
              headerName: 'Scorers',
              flex: 1,
              valueGetter: (_, row) => row.obj.val['scorers'],
              renderCell: params => {
                const scorerRefs: string[] = params.value;
                return scorerRefs.length > 0 ? (
                  <div className="flex items-center gap-2">
                    <CellValue value={scorerRefs[0]} />
                    {scorerRefs.length > 1 ? (
                      <span>{`+${scorerRefs.length - 1}`}</span>
                    ) : null}
                  </div>
                ) : null;
              },
            },
            {
              field: 'active',
              headerName: 'Active',
              valueGetter: (_, row) => {
                return row.obj.val['active'];
              },
              renderCell: params => {
                return <CellValue value={params.value} />;
              },
            },
          ]}
        />
      </Box>
    </Tailwind>
  );
};
