import {renderHook, act} from '@testing-library/react';
import React from 'react';

import {useMagicGeneration} from '../hooks/useMagicGeneration';

// Mock the dependencies
jest.mock('../index', () => ({
  useChatCompletionStream: jest.fn(),
}));

jest.mock('../context', () => ({
  useMagicContext: jest.fn(() => ({
    entity: 'test-entity',
    project: 'test-project',
    selectedModel: 'test-model',
    setSelectedModel: jest.fn(),
  })),
}));

describe('useMagicGeneration', () => {
  const mockOnStream = jest.fn();
  const mockOnError = jest.fn();
  const mockOnCancel = jest.fn();
  const mockChatCompletionStream = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    const {useChatCompletionStream} = require('../index');
    useChatCompletionStream.mockReturnValue(mockChatCompletionStream);
  });

  it('should initialize with correct state', () => {
    const {result} = renderHook(() =>
      useMagicGeneration({
        systemPrompt: 'Test prompt',
        onStream: mockOnStream,
      })
    );

    expect(result.current.isGenerating).toBe(false);
    expect(typeof result.current.generate).toBe('function');
    expect(typeof result.current.cancel).toBe('function');
  });

  it('should handle generation successfully', async () => {
    const mockResponse = 'Generated content';
    mockChatCompletionStream.mockResolvedValue(mockResponse);

    const {result} = renderHook(() =>
      useMagicGeneration({
        systemPrompt: 'Test prompt',
        onStream: mockOnStream,
      })
    );

    await act(async () => {
      await result.current.generate('User instructions');
    });

    expect(mockOnStream).toHaveBeenCalledWith('', '', null, false); // Loading state
    expect(mockOnStream).toHaveBeenCalledWith('', mockResponse, mockResponse, true); // Completion
    expect(result.current.isGenerating).toBe(false);
  });

  it('should handle generation errors', async () => {
    const mockError = new Error('Generation failed');
    mockChatCompletionStream.mockRejectedValue(mockError);

    const {result} = renderHook(() =>
      useMagicGeneration({
        systemPrompt: 'Test prompt',
        onStream: mockOnStream,
        onError: mockOnError,
      })
    );

    await act(async () => {
      await result.current.generate('User instructions');
    });

    expect(mockOnError).toHaveBeenCalledWith(mockError);
    expect(result.current.isGenerating).toBe(false);
  });

  it('should handle cancellation', async () => {
    const {result} = renderHook(() =>
      useMagicGeneration({
        systemPrompt: 'Test prompt',
        onStream: mockOnStream,
        onCancel: mockOnCancel,
      })
    );

    act(() => {
      result.current.cancel();
    });

    expect(mockOnCancel).toHaveBeenCalled();
    expect(result.current.isGenerating).toBe(false);
  });

  it('should not generate with empty instructions', async () => {
    const {result} = renderHook(() =>
      useMagicGeneration({
        systemPrompt: 'Test prompt',
        onStream: mockOnStream,
      })
    );

    await act(async () => {
      await result.current.generate('');
    });

    expect(mockChatCompletionStream).not.toHaveBeenCalled();
    expect(mockOnStream).not.toHaveBeenCalled();
  });
}); 