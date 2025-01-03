import {Box, Chip, TextField} from '@mui/material';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import React, {KeyboardEvent, useState} from 'react';

type StopSequenceEditorProps = {
  stopSequences: string[];
  setStopSequences: (value: string[]) => void;
};

export const StopSequenceEditor: React.FC<StopSequenceEditorProps> = ({
  stopSequences,
  setStopSequences,
}) => {
  const [currentStopSequence, setCurrentStopSequence] = useState('');

  const handleStopSequenceKeyDown = (
    event: KeyboardEvent<HTMLInputElement>
  ) => {
    if (event.key === 'Enter' && currentStopSequence.trim() !== '') {
      if (!stopSequences.includes(currentStopSequence.trim())) {
        setStopSequences([...stopSequences, currentStopSequence.trim()]);
      }
      setCurrentStopSequence('');
    }
  };

  const handleDeleteStopSequence = (sequenceToDelete: string) => {
    setStopSequences(stopSequences.filter(seq => seq !== sequenceToDelete));
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        width: '100%',
      }}>
      <span style={{fontSize: '14px'}}>Stop sequences</span>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          border: `1px solid ${MOON_250}`,
          ...(stopSequences.length > 0
            ? {padding: '8px', paddingBottom: 0}
            : {}),
          borderRadius: '4px',
          width: '100%',
        }}>
        <Box sx={{display: 'flex', flexWrap: 'wrap', gap: 1, width: '100%'}}>
          {stopSequences.map((seq, index) => (
            <Chip
              key={index}
              label={seq}
              onDelete={() => handleDeleteStopSequence(seq)}
              size="small"
            />
          ))}
        </Box>
        <TextField
          value={currentStopSequence}
          onChange={e => setCurrentStopSequence(e.target.value)}
          onKeyDown={handleStopSequenceKeyDown}
          placeholder="Type and press Enter"
          size="small"
          fullWidth
          variant="standard"
          slotProps={{
            input: {
              disableUnderline: true,
            },
          }}
          sx={{
            fontFamily: 'Source Sans Pro',
            '& .MuiInputBase-root': {
              border: 'none',
              '&:before, &:after': {
                borderBottom: 'none',
              },
              '&:hover:not(.Mui-disabled):before': {
                borderBottom: 'none',
              },
            },
            '& .MuiInputBase-input': {
              padding: '8px',
              fontFamily: 'Source Sans Pro',
            },
          }}
        />
      </Box>
    </Box>
  );
};
