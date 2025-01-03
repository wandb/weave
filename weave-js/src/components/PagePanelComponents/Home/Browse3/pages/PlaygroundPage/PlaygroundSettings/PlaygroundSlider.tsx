import {Box} from '@material-ui/core';
import {TextField} from '@mui/material';
import Slider from '@mui/material/Slider';
import {styled} from '@mui/material/styles';
import {
  MOON_200,
  MOON_250,
  MOON_350,
  TEAL_500,
} from '@wandb/weave/common/css/color.styles';
import {isArray} from 'lodash';
import React, {useEffect} from 'react';

export const StyledSlider = styled(Slider)(({theme}) => ({
  color: MOON_250,
  height: 4,
  marginBottom: 0,
  padding: 0,
  // So that the track lines up with the margin
  width: 'calc( 100% - 12px )',
  '& .MuiSlider-thumb': {
    height: 12,
    width: 12,
    backgroundColor: '#fff',
    boxShadow: '0 0 2px 0px rgba(0, 0, 0, 0.1)',
    marginLeft: 6,
    marginRight: 6,
    border: `1px solid ${MOON_350}`,
    '&:focus, &:hover, &.Mui-active': {
      boxShadow: '0px 0px 0px 0px rgba(0, 0, 0, 0.1)',
      '@media (hover: none)': {
        boxShadow:
          '0px 0px 0px 0px rgba(0,0,0,0.2), 0px 0px 0px 0px rgba(0,0,0,0.14), 0px 0px 1px 0px rgba(0,0,0,0.12)',
      },
    },
    '&:after': {
      height: 12,
      width: 12,
    },
  },
  '& .MuiSlider-track': {
    border: 'none',
    height: 4,
    backgroundColor: TEAL_500,
  },
  '& .MuiSlider-rail': {
    opacity: 1,
    backgroundColor: MOON_250,
    paddingRight: 12,
  },
}));

type PlaygroundSliderProps = {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  setValue: (value: number) => void;
};

export const PlaygroundSlider = ({
  setValue,
  ...props
}: PlaygroundSliderProps) => {
  const [editing, setEditing] = React.useState<string | null>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEditing(e.target.value);
  };

  const handleInputBlur = (): void => {
    if (editing !== null) {
      const newValue = parseFloat(editing);
      if (!isNaN(newValue)) {
        setValue(newValue);
      }
      setEditing(null);
    }
  };

  const handleInputKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleInputBlur();
    }
  };

  useEffect(() => {
    if (props.value < props.min) {
      setValue(props.min);
    } else if (props.value > props.max) {
      setValue(props.max);
    }
  }, [props.value, props.min, props.max, setValue]);

  return (
    <Box sx={{lineHeight: '14px'}}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
        <span style={{fontSize: '14px'}}>{props.label}</span>
        <TextField
          value={
            editing !== null
              ? editing
              : formatValueToStep(props.value, props.step)
          }
          onChange={handleInputChange}
          onBlur={handleInputBlur}
          onKeyDown={handleInputKeyPress}
          variant="standard"
          slotProps={{
            input: {
              disableUnderline: true,
            },
          }}
          size="small"
          sx={{
            width: 50,
            '& input': {
              fontFamily: 'Source Sans Pro',
              fontSize: '14px',
              padding: '0 2px',
              textAlign: 'right',
              borderRadius: '4px',
              '&:hover': {
                backgroundColor: MOON_200,
              },
            },
          }}
        />
      </Box>
      <StyledSlider
        onChange={(e, value) => {
          if (isArray(value)) {
            setValue(value[0]);
          } else {
            setValue(value);
          }
        }}
        {...props}
      />
    </Box>
  );
};

export const formatValueToStep = (value: number, step: number): string => {
  if (step >= 1) {
    return value.toFixed(0);
  }

  const decimalPlaces = Math.max(0, -Math.floor(Math.log10(step)));
  return value.toFixed(decimalPlaces);
};
