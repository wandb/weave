import * as _ from 'lodash';
import React, {FC, useMemo, useState} from 'react';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {flatToTrees} from '../../../Panel2/PanelTraceTree/util';
import {
  Span,
  StreamId,
  feedbackTableObjNode,
  listSelectAll,
  runFeedbackNode,
} from './callTree';
import {v4 as uuidv4} from 'uuid';
import {Paper} from './CommonLib';
import {useTraceSpans} from './callTreeHooks';
import {Button, Typography, Box, Grid, Tabs, Tab} from '@mui/material';
import {AddRowToTable} from './AddRow';
import {SpanDetails} from './SpanDetails';
import {SpanWithChildren, SpanTreeNode} from './SpanWithChildren';
import {useNodeValue} from '@wandb/weave/react';
import {ObjectEditor, useObjectEditorState} from './ObjectEditor';
import {mutationStreamTableLog} from './easyWeave';
import {useWeaveContext} from '@wandb/weave/context';

const VerticalTraceView: FC<{
  traceSpans: Span[];
  selectedSpanId?: string;
  setSelectedSpanId: (spanId: string) => void;
  callStyle: 'full' | 'short';
}> = ({traceSpans, selectedSpanId, setSelectedSpanId}) => {
  const tree = useMemo(
    () => flatToTrees(traceSpans),
    [traceSpans]
  ) as SpanWithChildren[];

  return tree[0] == null ? (
    <div>No trace spans found</div>
  ) : (
    <SpanTreeNode
      call={tree[0]}
      selectedSpanId={selectedSpanId}
      setSelectedSpanId={setSelectedSpanId}
    />
  );
};

const SpanFeedback: FC<{streamId: StreamId; spanId: string}> = ({
  streamId,
  spanId,
}) => {
  const feedbackNode = listSelectAll(
    runFeedbackNode(streamId.entityName, streamId.projectName, spanId)
  );
  const feedbackQuery = useNodeValue(feedbackNode);
  const feedback = feedbackQuery.result ?? [];
  const lastFeedback = feedback[feedback.length - 1]?.feedback ?? {};
  console.log('FEEDBACKQUERY', feedbackQuery);

  return feedbackQuery.loading ? (
    <div>loading...</div>
  ) : (
    <SpanFeedbackLoaded {...{streamId, spanId, lastFeedback}} />
  );
};

const SpanFeedbackLoaded: FC<{
  streamId: StreamId;
  spanId: string;
  lastFeedback: {[key: string]: any};
}> = ({streamId, spanId, lastFeedback}) => {
  const weave = useWeaveContext();
  const {
    value: feedbackValue,
    valid: feedbackValid,
    props: objectEditorProps,
  } = useObjectEditorState(lastFeedback);

  return (
    <>
      <ObjectEditor {...objectEditorProps} label="Feedback" />
      <Box display="flex" justifyContent="flex-end" pt={2}>
        <Button
          disabled={!feedbackValid}
          onClick={() =>
            mutationStreamTableLog(
              weave,
              feedbackTableObjNode(streamId.entityName, streamId.projectName),
              {
                run_id: spanId,
                feedback_id: uuidv4(),
                feedback: feedbackValue,
              }
            )
          }>
          Update
        </Button>
      </Box>
    </>
  );
};

export const Browse2Trace: FC<{
  streamId: StreamId;
  traceId: string;
  spanId?: string;
  setSelectedSpanId: (spanId: string) => void;
}> = ({streamId, traceId, spanId, setSelectedSpanId}) => {
  const traceSpans = useTraceSpans(streamId, traceId);
  const selectedSpanId = spanId;
  const selectedSpan = useMemo(() => {
    if (selectedSpanId == null) {
      return undefined;
    }
    return traceSpans.filter(ts => ts.span_id === selectedSpanId)[0];
  }, [selectedSpanId, traceSpans]);
  const simpleInputOutputValue = useMemo(() => {
    if (selectedSpan == null) {
      return undefined;
    }
    const simpleInputOrder =
      selectedSpan.inputs._input_order ??
      Object.keys(selectedSpan.inputs).filter(
        k => !k.startsWith('_') && k !== 'self'
      );
    const simpleInputs = _.fromPairs(
      simpleInputOrder
        .map(k => [k, selectedSpan.inputs[k]])
        .filter(([k, v]) => v != null)
    );

    let output = selectedSpan.output;
    if (output == null) {
      output = {_result: null};
    }
    const simpleOutput = _.fromPairs(
      Object.entries(output).filter(([k, v]) => v != null)
    );

    return {
      input: simpleInputs,
      output: simpleOutput,
    };
  }, [selectedSpan]);
  const [tabId, setTabId] = React.useState(0);
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabId(newValue);
  };

  const [addRowToTableOpen, setAddRowToTableOpen] = useState(false);

  return (
    <Grid container spacing={2} alignItems="flex-start">
      <Grid xs={3} item>
        <Paper>
          <VerticalTraceView
            traceSpans={traceSpans}
            selectedSpanId={selectedSpanId}
            setSelectedSpanId={setSelectedSpanId}
            callStyle="short"
          />
        </Paper>
      </Grid>
      <Grid xs={9} item>
        {selectedSpanId != null && (
          <Paper>
            <Tabs value={tabId} onChange={handleTabChange}>
              <Tab label="Run" />
              <Tab label="Feedback" />
              <Tab label="Datasets" />
            </Tabs>
            <Box pt={2}>
              {tabId === 0 &&
                (selectedSpan == null ? (
                  <div>Span not found</div>
                ) : (
                  <SpanDetails call={selectedSpan} />
                ))}
              {tabId === 1 && (
                <SpanFeedback streamId={streamId} spanId={selectedSpanId} />
              )}
              {tabId === 2 && (
                <>
                  <Typography variant="h6" gutterBottom>
                    Appears in datasets
                  </Typography>
                  <Box
                    mb={4}
                    sx={{
                      background: globals.lightYellow,
                      height: 200,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                    Placeholder
                  </Box>
                  <Button
                    variant="outlined"
                    onClick={() => setAddRowToTableOpen(true)}>
                    Add to dataset
                  </Button>
                  {addRowToTableOpen && (
                    <AddRowToTable
                      entityName={streamId.entityName}
                      open={addRowToTableOpen}
                      handleClose={() => setAddRowToTableOpen(false)}
                      initialFormState={{
                        projectName: streamId.projectName,
                        row: simpleInputOutputValue,
                      }}
                    />
                  )}
                </>
              )}
            </Box>
          </Paper>
        )}
      </Grid>
    </Grid>
  );
};
