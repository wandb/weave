import React, { useEffect, useState } from 'react';
import {
    Dialog,
    DialogActions as MaterialDialogActions,
    DialogContent as MaterialDialogContent,
    DialogTitle as MaterialDialogTitle,
  } from '@material-ui/core';
import { Button } from '@wandb/weave/components/Button';
import styled from 'styled-components';
import { useGetTraceServerClientContext } from '../../pages/wfReactInterface/traceServerClientContext';
import { Tailwind } from '@wandb/weave/components/Tailwind';
import { TextField } from '@wandb/weave/components/Form/TextField';
import { Autocomplete, TextField as MuiTextField } from '@mui/material';
import { MOON_300 } from '@wandb/weave/common/css/color.styles';

type BaseFeedback = {
    name: string,
    ref?: string,
}

type NumericalFeedback = BaseFeedback & {
    type: "NumericalFeedback",
    min: number,
    max: number,
}

type TextFeedback = BaseFeedback & {
    type: "TextFeedback",
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

type StructuredFeedback = CategoricalFeedback | NumericalFeedback | TextFeedback | BooleanFeedback | EmojiFeedback;

type StructuredFeedbackSpec = {
    _bases?: string[],
    _class_name?: string,

    types: StructuredFeedback[],
    ref?: string,
}

const FEEDBACK_TYPE_OPTIONS = [
    {"name": "Numerical feedback", "value": "NumericalFeedback"},
    {"name": "Text feedback", "value": "TextFeedback"},
    {"name": "Categorical feedback", "value": "CategoricalFeedback"},
    {"name": "Boolean feedback", "value": "BooleanFeedback"},
    {"name": "Emoji feedback", "value": "EmojiFeedback"},
];


const NumericalFeedbackComponent = ({ min, max, onSetMin, onSetMax }: { min?: number, max?: number, onSetMin: (value: number) => void, onSetMax: (value: number) => void }) => (
    <div className="flex flex-col">
        <span className="text-xs text-moon-500 mb-2">optional</span>
        <div className="flex items-center space-x-4 pb-8">
            <div className="items-center w-full">
                <span className="text-s font-bold text-moon-600 mx-4">min</span>
                <TextField
                    value={min?.toString() ?? undefined}
                    type="number"
                    onChange={(value) => onSetMin(Number(value))}
                    placeholder="min"
                />
            </div>
            <div className="items-center w-full">
                <span className="text-s font-bold text-moon-600 mx-4">max</span>
                <TextField
                    value={max?.toString() ?? undefined}
                    type="number"
                    onChange={(value) => onSetMax(Number(value))}
                    placeholder="max"
                />
            </div>
        </div>
    </div>
);

const CategoricalFeedbackComponent = ({ options, setOptions }: { options: string[], setOptions: (options: string[]) => void }) => {
    const [newOption, setNewOption] = useState<string>("");

    return (
        <div className="my-8">
            <span className='p-4 font-semibold'>Add Options</span>
            <div className="flex items-center space-x-2">
                <TextField
                    value={newOption}
                    onChange={(value) => setNewOption(value)}
                    placeholder="Enter option"
                />
                <Button
                    variant="ghost"
                    onClick={() => {
                        if (newOption.trim() !== "") {
                            setOptions([...options, newOption.trim()]);
                            setNewOption("");
                        }
                    }}
                >
                    Add
                </Button>
            </div>
            <div className="mt-4">
                {options.map((option, index) => (
                    <div key={index} className="flex items-center justify-between">
                        <span>{option}</span>
                        <Button
                            icon="delete"
                            variant="ghost"
                            onClick={() => {
                                setOptions(options.filter((_, i) => i !== index));
                            }}
                        />
                    </div>
                ))}
            </div>
        </div>
    );
};

const createStructuredFeedback = (type: string, name: string, min?: number, max?: number, options?: string[]): StructuredFeedback => {
    // validate min and max
    switch (type) {
        case "NumericalFeedback":
            // validate min and max dont conflict
            if (min && max && min > max) {
                throw new Error("Min is greater than max");
            }
            return { type: "NumericalFeedback", name, min: min!, max: max! };
        case "TextFeedback":
            return { type: "TextFeedback", name };
        case "CategoricalFeedback":
            return { type: "CategoricalFeedback", name, options: options!, multiSelect: false, addNewOption: false };
        case "BooleanFeedback":
            return { type: "BooleanFeedback", name };
        case "EmojiFeedback":
            return { type: "EmojiFeedback", name };
        default:
            throw new Error("Invalid feedback type");
    }
};

const FeedbackTypeSelector = ({ selectedFeedbackType, setSelectedFeedbackType, feedbackTypeOptions, readOnly }: { selectedFeedbackType: string, setSelectedFeedbackType: (value: string) => void, feedbackTypeOptions: { name: string, value: string }[], readOnly?: boolean }) => {
    return (
    <div className='my-8'>
        <span className='p-4 font-semibold'>Metric type</span>
        <Autocomplete
            options={feedbackTypeOptions}
            getOptionLabel={(option) => option.name}
            onChange={(e, newValue) => setSelectedFeedbackType(newValue?.value ?? '')}
            value={feedbackTypeOptions.find(option => option.value === selectedFeedbackType)}
            renderInput={(params) => (
                <MuiTextField
                    {...params}
                    sx={{
                        '& .MuiInputBase-root': {
                            height: '38px',
                            minHeight: '38px',
                            borderColor: MOON_300,
                        },
                        '& .MuiOutlinedInput-notchedOutline': {
                            borderColor: MOON_300,
                        },
                        '&:hover .MuiOutlinedInput-notchedOutline': {
                            borderColor: MOON_300,
                        },
                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                            borderColor: MOON_300,
                        },
                    }}
                    placeholder="Select feedback type"
                />
            )}
            disableClearable
            sx={{
                minWidth: '244px',
                width: 'auto',
            }}
            fullWidth
            ListboxProps={{
                style: {
                    maxHeight: '200px',
                },
            }}
            disabled={readOnly}
            renderOption={(props, option) => (
                <li {...props} style={{ minHeight: '30px' }}>
                    {option.name || <span>&nbsp;</span>}
                </li>
            )}
        />
    </div>
    );
};

const submitStructuredFeedback = (
    entity: string,
    project: string,
    newFeedback: StructuredFeedback,
    existingFeedbackColumns: StructuredFeedback[],
    editColumnName: string | null,
    getTsClient: () => any,
    onClose: () => void
) => {
    
    const tsClient = getTsClient();
    let updatedTypes: StructuredFeedback[];

    if (editColumnName) {
        updatedTypes = existingFeedbackColumns.map(t => 
            t.name === editColumnName ? newFeedback : t
        );
    } else {
        updatedTypes = [...existingFeedbackColumns, newFeedback];
    }

    const value: StructuredFeedbackSpec = {
        _bases: ["StructuredFeedback", "Object", "BaseModel"],
        _class_name: "StructuredFeedback",
        types: updatedTypes,
    }

    const req = {
        obj: {
            project_id: `${entity}/${project}`,
            object_id: "StructuredFeedback-obj",
            val: value,
        }
    };
    
    tsClient.objCreate(req).then(() => {
        onClose();
    }).catch((e: any) => {
        console.error(`Error ${editColumnName ? 'updating' : 'creating'} structured feedback`, e);
    });
};

const CreateStructuredFeedbackModal = ({ entity, project, existingFeedbackColumns, onClose }: { entity: string, project: string, existingFeedbackColumns: StructuredFeedback[], onClose: () => void }) => {
    const [open, setOpen] = useState(true);
    const [nameField, setNameField] = useState<string>("");
    const [selectedFeedbackType, setSelectedFeedbackType] = useState<string>("Numerical feedback");
    const [minValue, setMinValue] = useState<number | undefined>(undefined);
    const [maxValue, setMaxValue] = useState<number | undefined>(undefined);
    const [categoricalOptions, setCategoricalOptions] = useState<string[]>([]);
    const getTsClient = useGetTraceServerClientContext();

    const submit = () => {
        const option = FEEDBACK_TYPE_OPTIONS.find((o) => o.value === selectedFeedbackType);
        if (!option) {
            console.error(`Invalid feedback type: ${selectedFeedbackType}, options: ${FEEDBACK_TYPE_OPTIONS.map((o) => o.value).join(', ')}`);
            return;
        }
        let newFeedback;
        try {
            newFeedback = createStructuredFeedback(
                option.value,
                nameField,
                minValue,
                maxValue,
                categoricalOptions
            );
        } catch (e) {
            console.error(e);
            return;
        }
        submitStructuredFeedback(entity, project, newFeedback, existingFeedbackColumns, null, getTsClient, onClose);
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
            <Tailwind>
          <DialogTitle>Add feedback column</DialogTitle>
          <DialogContent style={{overflow: 'hidden'}}>
            <div className='my-8'>
                <span className='p-4 font-semibold'>Metric name</span>
                <TextField value={nameField} onChange={(value) => setNameField(value)} placeholder='...'/>
            </div>
            <FeedbackTypeSelector
                feedbackTypeOptions={FEEDBACK_TYPE_OPTIONS}
                selectedFeedbackType={selectedFeedbackType}
                setSelectedFeedbackType={setSelectedFeedbackType}
            />
            {selectedFeedbackType === "NumericalFeedback" && (
                <NumericalFeedbackComponent
                    onSetMin={setMinValue}
                    onSetMax={setMaxValue}
                />
            )}
            {selectedFeedbackType === "CategoricalFeedback" && (
                <CategoricalFeedbackComponent
                    options={categoricalOptions}
                    setOptions={setCategoricalOptions}
                />
            )}
          </DialogContent>
          <DialogActions $align="left">
          <Button
              variant="ghost"
              disabled={selectedFeedbackType === ""}
              onClick={submit}>
              Add column
            </Button>
          </DialogActions>
            </Tailwind>
        </Dialog>
    );
}

const EditStructuredFeedbackModal = ({ entity, project, structuredFeedbackData, editColumnName, onClose }: { entity: string, project: string, structuredFeedbackData: StructuredFeedbackSpec, editColumnName: string, onClose: () => void }) => {
    console.log(structuredFeedbackData, editColumnName);
    const feedbackColumn = structuredFeedbackData.types.find((t) => t.name === editColumnName);
    if (!feedbackColumn) {
        console.error(`Structured feedback column not found: ${editColumnName}`, structuredFeedbackData);
        return <></>
    }

    const [open, setOpen] = useState(true);
    const [nameField, setNameField] = useState<string>(feedbackColumn.name);
    const [selectedFeedbackType, setSelectedFeedbackType] = useState<string>(feedbackColumn.type);
    const [minValue, setMinValue] = useState<number | undefined>('min' in feedbackColumn ? feedbackColumn.min : undefined);
    const [maxValue, setMaxValue] = useState<number | undefined>('max' in feedbackColumn ? feedbackColumn.max : undefined);
    const [categoricalOptions, setCategoricalOptions] = useState<string[]>('options' in feedbackColumn ? feedbackColumn.options : []);

    const getTsClient = useGetTraceServerClientContext();

    const submit = () => {
        let updatedFeedbackColumn;
        try {
            updatedFeedbackColumn = createStructuredFeedback(
                selectedFeedbackType,
                nameField,
                minValue,
                maxValue,
                categoricalOptions
            );
        } catch (e) {
            console.error(e);
            return;
        }
        submitStructuredFeedback(entity, project, updatedFeedbackColumn, structuredFeedbackData.types, editColumnName, getTsClient, onClose);
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
            <Tailwind>
          <DialogTitle>Edit structured feedback</DialogTitle>
          <DialogContent style={{overflow: 'hidden'}}>
            <div className='my-8'>
                <span className='p-4 font-semibold'>Metric name</span>
                <TextField value={nameField} onChange={(value) => setNameField(value)} placeholder='...'/>
            </div>
            <FeedbackTypeSelector
                feedbackTypeOptions={FEEDBACK_TYPE_OPTIONS}
                selectedFeedbackType={selectedFeedbackType}
                setSelectedFeedbackType={setSelectedFeedbackType}
                readOnly={true}
            />
            {selectedFeedbackType === "NumericalFeedback" && (
                <NumericalFeedbackComponent
                    min={minValue}
                    max={maxValue}
                    onSetMin={setMinValue}
                    onSetMax={setMaxValue}
                />
            )}
            {selectedFeedbackType === "CategoricalFeedback" && (
                <CategoricalFeedbackComponent
                    options={categoricalOptions}
                    setOptions={setCategoricalOptions}
                />
            )}
          </DialogContent>
          <DialogActions $align="left">
            <Button
              variant="ghost"
              onClick={submit}>
              Update
            </Button>
          </DialogActions>
            </Tailwind>
        </Dialog>
    );
}

export const ConfigureStructuredFeedbackModal = ({ entity, project, structuredFeedbackData, editColumnName, onClose }: { entity: string, project: string, structuredFeedbackData?: StructuredFeedbackSpec, editColumnName?: string, onClose: () => void }) => {
    if (editColumnName && structuredFeedbackData) {
        return <EditStructuredFeedbackModal
            entity={entity}
            project={project}
            structuredFeedbackData={structuredFeedbackData}
            editColumnName={editColumnName}
            onClose={onClose}
        />
    } else {
        return <CreateStructuredFeedbackModal
            entity={entity}
            project={project}
            onClose={onClose}
            existingFeedbackColumns={structuredFeedbackData?.types ?? []}
        />
    }
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

