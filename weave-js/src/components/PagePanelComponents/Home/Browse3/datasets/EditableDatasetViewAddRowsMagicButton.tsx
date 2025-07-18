import {MagicButton} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/magician';
import React, {useCallback, useMemo, useRef} from 'react';
import z from 'zod';

const BUTTON_TEXT = 'Generate Rows';
const SYSTEM_PROMPT = `
You are an LLM developer building a dataset.
Your goal is to extend the dataset with additional rows.
Make sure to exactly match the schema of the existing rows.
The values will always be stringified and parsed back into the correct type.
`;
const PLACEHOLDER = 'What do you want these rows to cover?';

type EditableDatasetViewAddRowsMagicButtonAdditionalProps = {
  exampleRows: Array<Record<string, any>>;
  numRowsToGenerate: number;
  onRowGenerated: (row: Record<string, any>) => void;
};

type EditableDatasetViewAddRowsMagicButtonProps =
  EditableDatasetViewAddRowsMagicButtonAdditionalProps &
    Omit<
      React.ComponentProps<typeof MagicButton>,
      'systemPrompt' | 'placeholder' | 'onStream'
    >;

export const EditableDatasetViewAddRowsMagicButton: React.FC<
  EditableDatasetViewAddRowsMagicButtonProps
> = props => {
  const keys = useMemo(() => {
    return Object.keys(props.exampleRows[0]);
  }, [props.exampleRows]);

  const responseFormat = useMemo(() => {
    return z.object({
      rows: z
        .array(z.object(Object.fromEntries(keys.map(key => [key, z.string()]))))
        .length(props.numRowsToGenerate),
    });
  }, [keys, props.numRowsToGenerate]);

  const exampleRowsStringified = useMemo(() => {
    return props.exampleRows.map((row: {[key: string]: any}) => {
      return Object.fromEntries(
        Object.entries(row).map(([key, value]) => [key, JSON.stringify(value)])
      );
    });
  }, [props.exampleRows]);

  const lastGeneratedIndex = useRef(-1);

  const parsePartialLLMRows = useCallback(
    (partialRows: string) => {
      let newRows: any[] = [];
      let remainingGuess = partialRows;
      while (remainingGuess.length > 0) {
        try {
          newRows = JSON.parse(remainingGuess).rows;
          break;
        } catch (e) {
          try {
            newRows = JSON.parse(remainingGuess + ']}').rows;
            console.log(newRows);
            break;
          } catch (e) {
            const parts = remainingGuess.split('}');
            if (parts.length <= 1) {
              break;
            }
            remainingGuess = parts.slice(0, -1).join('}') + '}';
          }
        }
      }

      const parsedRows = newRows.map(row => {
        return Object.fromEntries(
          keys.map(key => {
            const value = row[key] ?? '';
            try {
              return [key, JSON.parse(value)];
            } catch (e) {
              return [key, value];
            }
          })
        );
      });
      return parsedRows;
    },
    [keys]
  );

  return (
    <MagicButton
      onStream={(
        chunk: string,
        accumulation: string,
        parsedCompletion: any,
        isComplete: boolean
      ) => {
        const newRows = parsePartialLLMRows(accumulation);
        if (newRows.length > lastGeneratedIndex.current + 1) {
          const rowsToAdd = newRows.slice(lastGeneratedIndex.current + 1);
          rowsToAdd.forEach(row => {
            props.onRowGenerated(row);
          });
          lastGeneratedIndex.current = newRows.length - 1;
        }
        if (isComplete) {
          lastGeneratedIndex.current = -1;
        }
      }}
      systemPrompt={SYSTEM_PROMPT}
      placeholder={PLACEHOLDER}
      additionalContext={{
        existingRows: exampleRowsStringified,
      }}
      responseFormat={responseFormat}
      text={BUTTON_TEXT}
      _dangerousExtraAttributesToLog={{
        feature: 'add_rows',
      }}
      {...props}
    />
  );
};
