import * as _ from 'lodash';
import React, {FC} from 'react';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {Call} from './callTree';
import {
  OpenAIChatInputView,
  OpenAIChatOutputView,
  isOpenAIChatInput,
  isOpenAIChatOutput,
} from './openai';
import {Button, Grid, Typography, Box, Chip} from '@mui/material';
import {DisplayControlChars} from './CommonLib';
import {SmallRef, parseRefMaybe} from './SmallRef';

const ObjectView: FC<{obj: any}> = ({obj}) => {
  if (_.isPlainObject(obj)) {
    return (
      <Grid container spacing={1}>
        {Object.entries(obj).flatMap(([key, value]) => {
          const singleRow = !_.isPlainObject(value);
          return [
            <Grid item key={key + '-key'} xs={singleRow ? 2 : 12}>
              <Typography>{key}</Typography>
            </Grid>,
            <Grid item key={key + '-value'} xs={singleRow ? 10 : 12}>
              <Box ml={singleRow ? 0 : 2}>
                <ObjectView obj={value} />
              </Box>
            </Grid>,
          ];
        })}
      </Grid>
    );
  }
  if (typeof obj === 'string') {
    const ref = parseRefMaybe(obj);
    if (ref != null) {
      return <SmallRef objRef={ref} />;
    }
    return <DisplayControlChars text={obj} />;
  }
  return <Typography>{JSON.stringify(obj)}</Typography>;
};

export const SpanDetails: FC<{call: Call}> = ({call}) => {
  const actualInputs = Object.entries(call.inputs).filter(
    ([k, c]) => c != null && !k.startsWith('_')
  );
  const inputs = _.fromPairs(actualInputs);
  return (
    <div style={{width: '100%'}}>
      <div style={{marginBottom: 24}}>
        <Box mb={2}>
          <Box display="flex" justifyContent="space-between">
            <Typography variant="h5" gutterBottom>
              Function
            </Typography>
            {isOpenAIChatInput(inputs) && (
              <Button
                variant="outlined"
                sx={{backgroundColor: globals.lightYellow}}>
                Open in LLM Playground
              </Button>
            )}
          </Box>
          {parseRefMaybe(call.name) != null ? (
            <SmallRef objRef={parseRefMaybe(call.name)!} />
          ) : (
            call.name
          )}
        </Box>
        <Typography variant="body2" gutterBottom>
          Status: {call.status_code}
        </Typography>
        {call.exception != null && (
          <Typography variant="body2" gutterBottom>
            {call.exception}
          </Typography>
        )}
      </div>
      {call.attributes != null && (
        <div style={{marginBottom: 12}}>
          <Typography variant="h6" gutterBottom>
            Attributes
          </Typography>
          <Box pl={2} pr={2}>
            <ObjectView
              obj={_.fromPairs(
                Object.entries(call.attributes).filter(([k, v]) => v != null)
              )}
            />
          </Box>
        </div>
      )}
      <div style={{marginBottom: 12}}>
        <Typography variant="h6" gutterBottom>
          Summary
        </Typography>
        <Box pl={2} pr={2}>
          <ObjectView
            obj={_.fromPairs(
              Object.entries(call.summary).filter(([k, v]) => v != null)
            )}
          />
        </Box>
      </div>
      <div style={{marginBottom: 24}}>
        <Typography variant="h5" gutterBottom>
          Inputs
        </Typography>
        <Box pl={2} pr={2}>
          {isOpenAIChatInput(inputs) ? (
            <OpenAIChatInputView chatInput={inputs} />
          ) : (
            <ObjectView obj={inputs} />
          )}
        </Box>
      </div>
      <div style={{marginBottom: 24}}>
        <Typography variant="h6" gutterBottom>
          Output
        </Typography>
        <Box pl={2} pr={2}>
          {call.output == null ? (
            <div>null</div>
          ) : isOpenAIChatOutput(call.output) ? (
            <OpenAIChatOutputView chatOutput={call.output} />
          ) : (
            <ObjectView
              obj={_.fromPairs(
                Object.entries(call.output).filter(
                  ([k, v]) =>
                    (k === '_result' || !k.startsWith('_')) && v != null
                )
              )}
            />
          )}
        </Box>
      </div>
    </div>
  );
};
