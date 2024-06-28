import {Card, CardContent, Grid, Typography} from '@mui/material';
import React from 'react';

import {ValueViewNumber} from '../CallPage/ValueViewNumber';

interface SubMetric {
  label: React.ReactNode;
  value: number;
}

interface MetricTileProps {
  title: string;
  subtitle: string;
  mainMetric: number;
  unit?: string;
  isGood: boolean;
  subMetric1: SubMetric;
  subMetric2: SubMetric;
}

const MetricTile: React.FC<MetricTileProps> = ({
  title,
  subtitle,
  mainMetric,
  isGood,
  unit,
  subMetric1,
  subMetric2,
}) => {
  return (
    <Card sx={{width: '100%', height: '100%'}}>
      <CardContent sx={{'&:last-child': {pb: '12px'}}}>
        <Typography
          variant="h6"
          sx={{
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            textAlign: 'center',
          }}>
          {title}
        </Typography>
        <Typography
          variant="subtitle1"
          color="textSecondary"
          sx={{
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            height: '1.5rem',
            textAlign: 'center',
          }}>
          {subtitle}
        </Typography>
        <Typography
          sx={{
            color: isGood ? 'success.main' : 'error.main',
            fontSize: '2rem',
            fontWeight: 'bold',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            textAlign: 'center',
          }}>
          <ValueViewNumber fractionDigits={4} value={mainMetric} /> {unit}
        </Typography>
        <Grid
          container
          // spacing={2}
          sx={{borderTop: '1px solid', borderColor: 'divider', pt: 1, mt: 1}}>
          <Grid item xs={6} sx={{textAlign: 'center'}}>
            <Typography variant="subtitle2" color="textSecondary">
              {subMetric1.label}
            </Typography>
            <Typography
              variant="body1"
              sx={{
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
              <ValueViewNumber fractionDigits={4} value={subMetric1.value} />{' '}
              {unit}
            </Typography>
          </Grid>
          <Grid item xs={6} sx={{textAlign: 'center'}}>
            <Typography variant="subtitle2" color="textSecondary">
              {subMetric2.label}
            </Typography>
            <Typography
              variant="body1"
              sx={{
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
              <ValueViewNumber fractionDigits={4} value={subMetric2.value} />{' '}
              {unit}
              {/* {subMetric2.value} */}
            </Typography>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default MetricTile;
