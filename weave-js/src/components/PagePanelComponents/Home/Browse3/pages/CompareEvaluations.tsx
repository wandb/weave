import {Box} from '@material-ui/core';
import {Circle} from '@mui/icons-material';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import * as Plotly from 'plotly.js';
import React, {useEffect, useRef} from 'react';

import {CallLink, ObjectVersionLink} from './common/Links';
import {SimplePageLayout} from './common/SimplePageLayout';

export const CompareEvaluationsPage: React.FC<{
  entity: string;
  project: string;
  evaluationCallIds: string[];
}> = props => {
  return (
    <SimplePageLayout
      title={'Compare Evaluations'}
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: <CompareEvaluationsPageInner />,
        },
      ]}
    />
  );
};

const PlotlyScatterPlot: React.FC<{}> = () => {
  const divRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    var trace2: Plotly.ScatterData = {
      x: [2, 3, 4, 5],
      y: [16, 5, 11, 9],
      mode: 'markers',
      type: 'scatter',
      marker: {color: 'green', size: 12},
    };

    var trace3 = {
      x: [1, 2, 3, 4],
      y: [12, 9, 15, 12],
      mode: 'markers',
      type: 'scatter',
      marker: {color: 'blue', size: 12},
    };

    const data = [trace2, trace3];
    Plotly.newPlot(
      divRef.current as any,
      data,
      {
        height: 300,
        title: '',
        margin: {
          l: 20, // legend
          r: 0,
          b: 20, // legend
          t: 0,
          pad: 0,
        },
      },
      {
        displayModeBar: false,
        responsive: true,
      }
    );
  }, []);

  return (
    <Box
      sx={{
        height: '300',
        width: '100%',
      }}>
      <div ref={divRef}></div>
    </Box>
  );
};

const CompareEvaluationsPageInner: React.FC<{}> = () => {
  return (
    <Box
      sx={{
        display: 'grid',
        width: '100%',
        height: '100%',
        gridGap: 10,
        gridTemplateColumns: '230px auto',
        padding: 10,
        overflow: 'auto',
      }}>
      <Box
        sx={{
          fontWeight: 'bold',
          fontSize: 24,
          padding: 10,
          textAlign: 'center',
        }}>
        <h3>Summary Metrics</h3>
      </Box>
      <BasicTable />
      <Box
        sx={{
          fontWeight: 'bold',
          fontSize: 24,
          padding: 10,
          textAlign: 'center',
        }}>
        <h3>Model Properties</h3>
      </Box>
      <BasicTable />
      {/* <Box></Box> */}
      <Box
        sx={{
          fontWeight: 'bold',
          fontSize: 24,
          padding: 10,
          textAlign: 'center',
        }}>
        <h3>Compare Models</h3>
      </Box>
      <Box
        sx={{
          height: '300px',
          width: '100%',
        }}>
        <PlotlyScatterPlot />
      </Box>
      <Box />
      <BasicTable />
    </Box>
  );
};

function createData(
  name: string,
  calories: number,
  fat: number,
  carbs: number,
  protein: number
) {
  return {name, calories, fat, carbs, protein};
}

const rows = [
  createData('Frozen yoghurt', 159, 6.0, 24, 4.0),
  createData('Ice cream sandwich', 237, 9.0, 37, 4.3),
  createData('Eclair', 262, 16.0, 24, 6.0),
  createData('Cupcake', 305, 3.7, 67, 4.3),
  createData('Gingerbread', 356, 16.0, 49, 3.9),
];

const BasicTable: React.FC = () => {
  return (
    // <TableContainer component={Paper}>
    <Table sx={{minWidth: 650}} aria-label="simple table">
      <TableHead>
        <TableRow>
          <TableCell></TableCell>
          <TableCell align="right">
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'row',
                padding: 10,
                border: '1px solid #aaa',
                borderRadius: '5px',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}>
              <Circle
                sx={{
                  color: 'green',
                }}
              />
              <Box>
                <CallLink
                  entityName={'wandb-smle'}
                  projectName={'weave-rag-lc-demo'}
                  opName={'Evaluation'}
                  callId={'c891fd73-2937-4d4e-9efb-147be0fd444b'}
                  fullWidth={true}
                />
              </Box>
            </Box>
          </TableCell>
          <TableCell align="right">
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'row',
                padding: 10,
                border: '1px solid #aaa',
                borderRadius: '5px',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}>
              <Circle
                sx={{
                  color: 'blue',
                }}
              />
              <Box>
                <ObjectVersionLink
                  entityName={'wandb-smle'}
                  projectName={'weave-rag-lc-demo'}
                  objectName={'RagModel'}
                  version={'j5VetZto0f9017qA8vzz6jox1Gs3n8wtAHGYUFXEQws'}
                  versionIndex={8}
                  fullWidth={true}
                />
              </Box>
            </Box>
          </TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map(row => (
          <TableRow
            key={row.name}
            sx={{'&:last-child td, &:last-child th': {border: 0}}}>
            <TableCell component="th" scope="row">
              {row.name}
            </TableCell>
            <TableCell align="right">{row.calories}</TableCell>
            <TableCell align="right">{row.fat}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
    // </TableContainer>
  );
};
