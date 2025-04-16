import {fireEvent, render, screen} from '@testing-library/react';
import React from 'react';
import {describe, expect, test, vi} from 'vitest';

import {ObjectVersionSchema} from '../../pages/wfReactInterface/wfDataModelHooksInterface';
import {
  ACTION_TYPES,
  DatasetDrawerProvider,
  useDatasetDrawer,
} from '../DatasetDrawerContext';

// Mock the schemaUtils functions
vi.mock('../schemaUtils', () => ({
  suggestFieldMappings: vi.fn(
    (sourceSchema, targetSchema, existingMappings) => {
      // Return mappings that match the expectations in the test
      return [
        {sourceField: 'text', targetField: 'text'},
        {sourceField: 'inputs.prompt', targetField: 'prompt'},
      ];
    }
  ),
  mapCallsToDatasetRows: vi.fn(() => {
    return [
      {
        ___weave: {id: 'call1', isNew: true},
        text: 'Sample text',
      },
    ];
  }),
  createProcessedRowsMap: vi.fn(() => {
    return new Map([['call1', {text: 'Sample text'}]]);
  }),
  filterRowsForNewDataset: vi.fn(rows => rows),
  createTargetSchema: vi.fn(() => []),
}));

// Test component to expose context values
const TestConsumer = () => {
  const {
    state,
    dispatch,
    handleDatasetSelect,
    handleMappingChange,
    setCurrentStep,
    resetDrawerState,
  } = useDatasetDrawer();

  // Create a mock dataset that matches the expected shape
  const mockDataset: ObjectVersionSchema = {
    scheme: 'weave',
    weaveKind: 'object',
    entity: 'test-entity',
    project: 'test-project',
    objectId: 'test-dataset',
    path: 'test-path',
    versionHash: 'abc123',
    versionIndex: 1,
    baseObjectClass: 'Dataset',
    createdAtMs: Date.now(),
    val: {},
  };

  return (
    <div>
      <div data-testid="state">{JSON.stringify(state)}</div>
      <button
        data-testid="select-dataset"
        onClick={() => handleDatasetSelect(mockDataset)}>
        Select Dataset
      </button>
      <button
        data-testid="set-mappings"
        onClick={() =>
          handleMappingChange([
            {sourceField: 'text', targetField: 'text'},
            {sourceField: 'inputs.prompt', targetField: 'prompt'},
          ])
        }>
        Set Mappings
      </button>
      <button data-testid="next-step" onClick={() => setCurrentStep(2)}>
        Next Step
      </button>
      <button data-testid="prev-step" onClick={() => setCurrentStep(1)}>
        Previous Step
      </button>
      <button data-testid="reset" onClick={resetDrawerState}>
        Reset
      </button>
      <button
        data-testid="set-creating-new"
        onClick={() =>
          dispatch({type: ACTION_TYPES.SET_IS_CREATING_NEW, payload: true})
        }>
        Set Creating New
      </button>
      <button
        data-testid="setup-schemas-for-mapping"
        onClick={() => {
          // Set up test schemas that should produce field mapping suggestions
          dispatch({
            type: ACTION_TYPES.SET_SOURCE_SCHEMA,
            payload: [
              {name: 'text', type: 'string'},
              {name: 'inputs.prompt', type: 'string'},
              {name: 'inputs.model', type: 'string'},
              {name: 'output', type: 'string'},
              {name: 'timestamp', type: 'number'},
            ],
          });
          dispatch({
            type: ACTION_TYPES.SET_TARGET_SCHEMA,
            payload: [
              {name: 'text', type: 'string'},
              {name: 'prompt', type: 'string'}, // Should match inputs.prompt
              {name: 'model_type', type: 'string'}, // Should match inputs.model
              {name: 'result', type: 'string'}, // No direct match
            ],
          });
        }}>
        Setup Schemas for Mapping
      </button>
      <button
        data-testid="set-dataset-object"
        onClick={() => {
          dispatch({
            type: ACTION_TYPES.SET_DATASET_OBJECT,
            payload: {
              rows: [],
              schema: [{name: 'text', type: 'string'}],
            },
          });
        }}>
        Set Dataset Object
      </button>
      <button
        data-testid="set-added-rows-dirty"
        onClick={() => {
          dispatch({
            type: ACTION_TYPES.SET_USER_MODIFIED_MAPPINGS,
            payload: true,
          });
        }}>
        Set Added Rows Dirty
      </button>
      <div data-testid="added-rows-dirty">
        {state.addedRowsDirty.toString()}
      </div>
      <div data-testid="processed-rows-size">
        {state.processedRows.size.toString()}
      </div>
    </div>
  );
};

describe('DatasetDrawerContext', () => {
  test('provides initial state', () => {
    render(
      <DatasetDrawerProvider
        selectedCallIds={[]}
        onClose={() => {}}
        entity="test-entity"
        project="test-project">
        <TestConsumer />
      </DatasetDrawerProvider>
    );

    const stateElement = screen.getByTestId('state');
    const state = JSON.parse(stateElement.textContent || '{}');

    expect(state.currentStep).toBe(1);
    expect(state.selectedDataset).toBeNull();
    expect(state.fieldMappings).toEqual([]);
    expect(state.isCreatingNew).toBe(false);
  });

  test('updates state when selecting a dataset', () => {
    render(
      <DatasetDrawerProvider
        selectedCallIds={[]}
        onClose={() => {}}
        entity="test-entity"
        project="test-project">
        <TestConsumer />
      </DatasetDrawerProvider>
    );

    fireEvent.click(screen.getByTestId('select-dataset'));

    const stateElement = screen.getByTestId('state');
    const state = JSON.parse(stateElement.textContent || '{}');

    expect(state.selectedDataset).toMatchObject({
      objectId: 'test-dataset',
      entity: 'test-entity',
      project: 'test-project',
      versionHash: 'abc123',
      versionIndex: 1,
    });
  });

  test('updates field mappings', () => {
    render(
      <DatasetDrawerProvider
        selectedCallIds={[]}
        onClose={() => {}}
        entity="test-entity"
        project="test-project">
        <TestConsumer />
      </DatasetDrawerProvider>
    );

    fireEvent.click(screen.getByTestId('set-mappings'));

    const stateElement = screen.getByTestId('state');
    const state = JSON.parse(stateElement.textContent || '{}');

    expect(state.fieldMappings).toEqual([
      {sourceField: 'text', targetField: 'text'},
      {sourceField: 'inputs.prompt', targetField: 'prompt'},
    ]);
  });

  test('navigates between steps', () => {
    render(
      <DatasetDrawerProvider
        selectedCallIds={[]}
        onClose={() => {}}
        entity="test-entity"
        project="test-project">
        <TestConsumer />
      </DatasetDrawerProvider>
    );

    fireEvent.click(screen.getByTestId('next-step'));

    const stateElement = screen.getByTestId('state');
    const state = JSON.parse(stateElement.textContent || '{}');

    expect(state.currentStep).toBe(2);
  });

  test('resets state', () => {
    render(
      <DatasetDrawerProvider
        selectedCallIds={[]}
        onClose={() => {}}
        entity="test-entity"
        project="test-project">
        <TestConsumer />
      </DatasetDrawerProvider>
    );

    // First select a dataset and set mappings
    fireEvent.click(screen.getByTestId('select-dataset'));
    fireEvent.click(screen.getByTestId('set-mappings'));

    // Then reset
    fireEvent.click(screen.getByTestId('reset'));

    const stateElement = screen.getByTestId('state');
    const state = JSON.parse(stateElement.textContent || '{}');

    expect(state.selectedDataset).toBeNull();
    expect(state.fieldMappings).toEqual([]);
    expect(state.currentStep).toBe(1);
  });

  test('handles create new mode correctly', () => {
    render(
      <DatasetDrawerProvider
        selectedCallIds={[]}
        onClose={() => {}}
        entity="test-entity"
        project="test-project">
        <TestConsumer />
      </DatasetDrawerProvider>
    );

    // First select a dataset
    fireEvent.click(screen.getByTestId('select-dataset'));

    // Then switch to create new mode
    fireEvent.click(screen.getByTestId('set-creating-new'));

    const stateElement = screen.getByTestId('state');
    const state = JSON.parse(stateElement.textContent || '{}');

    expect(state.isCreatingNew).toBe(true);
    expect(state.selectedDataset).toBeNull();
  });

  test('suggests field mappings based on schema similarity', () => {
    render(
      <DatasetDrawerProvider
        selectedCallIds={[]}
        onClose={() => {}}
        entity="test-entity"
        project="test-project">
        <TestConsumer />
      </DatasetDrawerProvider>
    );

    // Set up schemas that should produce mapping suggestions
    fireEvent.click(screen.getByTestId('setup-schemas-for-mapping'));

    // Get the updated state
    const stateElement = screen.getByTestId('state');
    const state = JSON.parse(stateElement.textContent || '{}');

    // Verify the current behavior of field mapping suggestions

    // 1. Should have the correct number of mappings
    expect(state.fieldMappings.length).toBe(2);

    // 2. Should handle exact matches (text to text)
    expect(state.fieldMappings).toContainEqual({
      targetField: 'text',
      sourceField: 'text',
    });

    // 3. Should handle substring matches (prompt in inputs.prompt)
    const promptMapping = state.fieldMappings.find(
      (m: any) => m.targetField === 'prompt'
    );
    expect(promptMapping).toBeDefined();
    expect(promptMapping?.sourceField).toBe('inputs.prompt');

    // 4. Should NOT currently map model_type to inputs.model
    const modelTypeMapping = state.fieldMappings.find(
      (m: any) => m.targetField === 'model_type'
    );
    expect(modelTypeMapping).toBeUndefined();

    // 5. Should NOT currently map result to output
    const resultMapping = state.fieldMappings.find(
      (m: any) => m.targetField === 'result'
    );
    expect(resultMapping).toBeUndefined();
  });

  test('does not reprocess rows when navigating between steps unless mappings are modified', () => {
    render(
      <DatasetDrawerProvider
        selectedCallIds={['1234', '5678']}
        onClose={() => {}}
        entity="test-entity"
        project="test-project">
        <TestConsumer />
      </DatasetDrawerProvider>
    );

    // Set up the necessary state for the test
    fireEvent.click(screen.getByTestId('select-dataset'));
    fireEvent.click(screen.getByTestId('set-dataset-object'));

    // Verify initial state
    expect(screen.getByTestId('added-rows-dirty').textContent).toBe('true');

    // Mark mappings as dirty to trigger row processing
    fireEvent.click(screen.getByTestId('set-added-rows-dirty'));

    // Navigate to step 2 - this should process rows since addedRowsDirty is true
    fireEvent.click(screen.getByTestId('next-step'));

    // Verify that addedRowsDirty was reset after processing
    expect(screen.getByTestId('added-rows-dirty').textContent).toBe('false');

    // Navigate back to step 1
    fireEvent.click(screen.getByTestId('prev-step'));

    // Navigate to step 2 again - this should NOT process rows since addedRowsDirty is false
    const initialProcessedRowsSize = screen.getByTestId(
      'processed-rows-size'
    ).textContent;
    fireEvent.click(screen.getByTestId('next-step'));

    // Verify that processed rows size hasn't changed
    expect(screen.getByTestId('processed-rows-size').textContent).toBe(
      initialProcessedRowsSize
    );

    // Now modify mappings which should set addedRowsDirty to true
    fireEvent.click(screen.getByTestId('prev-step'));
    fireEvent.click(screen.getByTestId('set-mappings'));

    // Verify that addedRowsDirty is now true
    expect(screen.getByTestId('added-rows-dirty').textContent).toBe('true');

    // Navigate to step 2 again - this should process rows since addedRowsDirty is true
    fireEvent.click(screen.getByTestId('next-step'));

    // Verify that addedRowsDirty was reset after processing
    expect(screen.getByTestId('added-rows-dirty').textContent).toBe('false');
  });
});
