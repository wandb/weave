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
import { CategoricalFeedbackColumn, RangeFeedbackColumn } from './StructuredFeedback';
import { useGetTraceServerClientContext } from '../../pages/wfReactInterface/traceServerClientContext';


type RangeFeedbackColumn = {
    type: "RangeFeedback",
    min: number,
    max: number,
}

type CategoricalFeedbackColumn = {
    type: "CategoricalFeedback",
    options: string[],
}

type StructuredFeedback = {
    _bases: string[],
    _class_name: string,

    types: (CategoricalFeedbackColumn | RangeFeedbackColumn)[],
}


export const AddStructuredFeedbackColumnModal = ({ entity, project, onClose }: { entity: string, project: string, onClose: () => void }) => {

    const [open, setOpen] = useState(true);
    const [exampleRangeFeedbackColumn, setExampleRangeFeedbackColumn] = useState<RangeFeedbackColumn>(
        {
            type: "RangeFeedback",
            min: 0,
            max: 100,
        }
    );
    const [exampleCategoricalFeedbackColumn, setExampleCategoricalFeedbackColumn] = useState<CategoricalFeedbackColumn>(
        {
            type: "CategoricalFeedback",
            options: ["Option 1", "Option 2"],
        }
    );

    const options = [
        {"name": "Range feedback", "value": exampleRangeFeedbackColumn},
        {"name": "Categorical feedback", "value": exampleCategoricalFeedbackColumn},
    ]

    const [selectedOption, setSelectedOption] = useState<string>(options[0].name);
    const getTsClient = useGetTraceServerClientContext();

    const onAddColumn = () => {
        const tsClient = getTsClient();
        const feedbackType = options.find(option => option.name === selectedOption)?.value;
        if (!feedbackType) {
            return;
        }
        const value: StructuredFeedback = {
            _bases: ["StructuredFeedback", "Object", "BaseModel"],
            _class_name: "StructuredFeedback",
            types: [feedbackType],
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

    return (
    <Dialog
      open={open}
      onClose={() => {
        setOpen(false);
        onClose();
      }}
      maxWidth="xs"
      fullWidth>
      <DialogTitle>Choose column type</DialogTitle>
      <DialogContent style={{overflow: 'hidden'}}>
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
            <CategoricalFeedbackColumn options={exampleCategoricalFeedbackColumn.options} defaultValue={null}/>
            </>
        )}
      </DialogContent>
      <DialogActions $align="left">
        <Button
          variant="ghost"
          onClick={onAddColumn}>
          Submit
        </Button>
      </DialogActions>
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