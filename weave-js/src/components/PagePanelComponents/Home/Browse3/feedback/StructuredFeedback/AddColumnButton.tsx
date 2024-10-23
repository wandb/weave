import React, { SyntheticEvent, useState } from 'react';
import {
    Dialog,
    DialogActions as MaterialDialogActions,
    DialogContent as MaterialDialogContent,
    DialogTitle as MaterialDialogTitle,
  } from '@material-ui/core';
import { Button } from '@wandb/weave/components/Button';
import styled from 'styled-components';
import { CodeEditor } from '@wandb/weave/components/CodeEditor';
import { BinaryFeedbackColumn, CategoricalFeedbackColumn, RangeFeedbackColumn } from './StructuredFeedback';
import { useGetTraceServerClientContext } from '../../pages/wfReactInterface/traceServerClientContext';
import { Tailwind } from '@wandb/weave/components/Tailwind';


type BaseFeedback = {
    name: string,
}

type RangeFeedback = BaseFeedback & {
    type: "RangeFeedback",
    min: number,
    max: number,
}

type CategoricalFeedback = BaseFeedback & {
    type: "CategoricalFeedback",
    options: string[],
    multiSelect: boolean,
    addNewOption: boolean,
}

type BooleanFeedback = BaseFeedback & {
    type: "BooleanFeedback",
}

type EmojiFeedback = BaseFeedback & {
    type: "EmojiFeedback",
}

type StructuredFeedback = CategoricalFeedback | RangeFeedback | BooleanFeedback | EmojiFeedback;

type StructuredFeedbackSpec = {
    _bases: string[],
    _class_name: string,

    types: StructuredFeedback[],
}


export const ConfigureStructuredFeedbackModal = ({ entity, project, existingFeedback, onClose }: { entity: string, project: string, existingFeedback: any, onClose: () => void }) => {

    const [open, setOpen] = useState(true);
    const [exampleRangeFeedbackColumn, setExampleRangeFeedbackColumn] = useState<StructuredFeedback>(
        {
            type: "RangeFeedback",
            name: "Example range feedback",
            min: 0,
            max: 100,
        }
    );
    const [exampleCategoricalFeedbackColumn, setExampleCategoricalFeedbackColumn] = useState<StructuredFeedback>(
        {
            type: "CategoricalFeedback",
            name: "Example categorical feedback",
            options: ["Option 1", "Option 2"],
            multiSelect: false,
            addNewOption: false,
        }
    );
    const [exampleBooleanFeedbackColumn, setExampleBooleanFeedbackColumn] = useState<StructuredFeedback>(
        {
            type: "BooleanFeedback",
            name: "Example boolean feedback",
        }
    );
    const [exampleEmojiFeedbackColumn, setExampleEmojiFeedbackColumn] = useState<StructuredFeedback>(
        {
            type: "EmojiFeedback",
            name: "Example emoji feedback",
        }
    );

    const options = [
        {"name": "Range feedback", "value": exampleRangeFeedbackColumn},
        {"name": "Categorical feedback", "value": exampleCategoricalFeedbackColumn},
        {"name": "Boolean feedback", "value": exampleBooleanFeedbackColumn},
        {"name": "Emoji feedback", "value": exampleEmojiFeedbackColumn},
    ]

    const [selectedOption, setSelectedOption] = useState<string>(options[0].name);
    const getTsClient = useGetTraceServerClientContext();

    const [feedbackColumns, setFeedbackColumns] = useState<StructuredFeedback[]>(existingFeedback?.types ?? []);

    const submit = () => {
        const tsClient = getTsClient();
        const value: StructuredFeedbackSpec = {
            _bases: ["StructuredFeedback", "Object", "BaseModel"],
            _class_name: "StructuredFeedback",
            types: feedbackColumns,
        }
        const req = {obj:{
            project_id: `${entity}/${project}`,
            object_id: "StructuredFeedback-obj",
            val: value,
        }}
        console.log("CREATING", req);
        tsClient.objCreate(req).then(() => {
            setOpen(false);
            onClose();
        }).catch((e) => {
            console.error("Error creating structured feedback", e);
        });
    }

    console.log(feedbackColumns)

    return (
    <Dialog
      open={open}
      onClose={() => {
        setOpen(false);
        onClose();
      }}
      maxWidth="xs"
      fullWidth>
        <Tailwind>
      <DialogTitle>Configure structured feedback</DialogTitle>
      <DialogContent style={{overflow: 'hidden'}}>
        <div>
            <h3>Existing structured feedback</h3>
            {feedbackColumns.map((feedback) => {
                return <div className='flex items-center'>
                    <div className='mr-4 text-moon-700 font-bold'>{feedback.name}</div>
                    <div>
                        <Button icon="delete" onClick={() => {
                            setFeedbackColumns(feedbackColumns.filter((t) => t.name !== feedback.name));
                        }}/>
                    </div>
                </div>
            })}
        </div>
        <h3>Add new structured feedback</h3>
        <select onChange={(e) => setSelectedOption(e.target.value)} value={selectedOption} className='w-full'>
        {options.map((option) => (
            <option key={option.name} value={option.name}>{option.name}</option>
        ))}
        </select>
        {selectedOption === "Range feedback" && (
            <>
            <CodeEditor 
                value={JSON.stringify(exampleRangeFeedbackColumn, null, 2)}
                language="json"
                onChange={(value) => {
                    setExampleRangeFeedbackColumn(JSON.parse(value));
                }}
            />
            <span>Example</span>
            <RangeFeedbackColumn min={exampleRangeFeedbackColumn.min} max={exampleRangeFeedbackColumn.max} defaultValue={null}/>
            </>
        )}
        {selectedOption === "Categorical feedback" && (
            <>
            <CodeEditor 
                value={JSON.stringify(exampleCategoricalFeedbackColumn, null, 2)}
                language="json"
                onChange={(value) => {
                    try {
                        setExampleCategoricalFeedbackColumn(JSON.parse(value));
                    } catch (e) {
                       
                    }
                }}
            />
            <span>Example</span>
            <CategoricalFeedbackColumn options={exampleCategoricalFeedbackColumn.options} defaultValue={null} multiSelect={exampleCategoricalFeedbackColumn.multiSelect} addNewOption={exampleCategoricalFeedbackColumn.addNewOption}/>
            </>
        )}
        {selectedOption === "Boolean feedback" && (
            <>
            <CodeEditor 
                value={JSON.stringify(exampleBooleanFeedbackColumn, null, 2)}
                language="json"
                onChange={(value) => {
                    setExampleBooleanFeedbackColumn(JSON.parse(value));
                }}
            />
            <span>Example</span>
            <BinaryFeedbackColumn defaultValue={null} onAddFeedback={(v, s) => Promise.resolve(true)} currentFeedbackId={null}/>
            </>
        )}
        <Button
          variant="ghost"
          disabled={selectedOption === ""}
          onClick={() => {
            const option = options.find((o) => o.name === selectedOption);
            if (option) {
                setFeedbackColumns([...feedbackColumns, option.value]);
            }
          }}>
          Add column
        </Button>
      </DialogContent>
      <DialogActions $align="left">
        <Button
          variant="ghost"
          onClick={submit}>
          Submit
        </Button>
            </DialogActions>
        </Tailwind>
    </Dialog>
  );
};

const DialogContent = styled(MaterialDialogContent)`
  padding: 0 32px !important;
`;
DialogContent.displayName = 'S.DialogContent';

const DialogTitle = styled(MaterialDialogTitle)`
  padding: 32px 32px 16px 32px !important;

  h2 {
    font-weight: 600;
    font-size: 24px;
    line-height: 30px;
  }
`;
DialogTitle.displayName = 'S.DialogTitle';

const DialogActions = styled(MaterialDialogActions)<{$align: string}>`
  justify-content: ${({$align}) =>
    $align === 'left' ? 'flex-start' : 'flex-end'} !important;
  padding: 32px 32px 32px 32px !important;
`;
DialogActions.displayName = 'S.DialogActions';