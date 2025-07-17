/**
 * Example usage of magician components
 *
 * This demonstrates how to integrate the simplified Magic components
 * into your React application.
 */

import React, {useState} from 'react';

import {
  ChatClientProvider,
  Chunk,
  MagicButton,
  MagicTooltip,
  useChatCompletionStream,
} from './index';

/**
 * Basic example showing tooltip integration
 */
export function BasicMagicExample() {
  const [generatedContent, setGeneratedContent] = useState('');

  const handleStream = (content: string, isComplete: boolean) => {
    setGeneratedContent(content);
  };

  const handleError = (error: Error) => {
    console.error('Generation error:', error);
  };

  return (
    <div>
      <MagicTooltip
        onStream={handleStream}
        onError={handleError}
        systemPrompt="You are a helpful assistant that generates clear, concise descriptions."
        placeholder="What would you like me to describe?"
        showModelSelector={true}>
        <MagicButton>Generate Description</MagicButton>
      </MagicTooltip>

      {generatedContent && (
        <div style={{marginTop: 20, padding: 10, border: '1px solid #ccc'}}>
          <h4>Generated Content:</h4>
          <p>{generatedContent}</p>
        </div>
      )}
    </div>
  );
}

/**
 * Example with content revision
 */
export function RevisionExample() {
  const [originalContent] = useState(
    'The quick brown fox jumps over the lazy dog.'
  );
  const [revisedContent, setRevisedContent] = useState('');

  const handleStream = (content: string, isComplete: boolean) => {
    setRevisedContent(content);
  };

  return (
    <div>
      <p>Original: {originalContent}</p>

      <MagicTooltip
        onStream={handleStream}
        systemPrompt="You are a helpful assistant that revises text based on user instructions."
        placeholder="How should I revise this text?"
        contentToRevise={originalContent}>
        <MagicButton>Revise Text</MagicButton>
      </MagicTooltip>

      {revisedContent && <p>Revised: {revisedContent}</p>}
    </div>
  );
}

/**
 * Example using completion hooks directly
 */
export function DirectHookExample() {
  const complete = useChatCompletionStream();
  const [output, setOutput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const generateHaiku = async () => {
    setIsLoading(true);
    setOutput('');

    try {
      await complete(
        {
          modelId: 'gpt-4o-mini',
          messages: 'Write a haiku about coding',
          temperature: 0.9,
        },
        (chunk: Chunk) => {
          setOutput(prev => prev + chunk.content);
        }
      );
    } catch (error) {
      console.error('Failed to generate:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <button onClick={generateHaiku} disabled={isLoading}>
        {isLoading ? 'Generating...' : 'Generate Haiku'}
      </button>
      {output && <pre>{output}</pre>}
    </div>
  );
}

/**
 * Complete app example with context provider
 */
export function MagicApp() {
  return (
    <ChatClientProvider value={{entity: 'my-org', project: 'my-project'}}>
      <div style={{padding: 20}}>
        <h1>magician Examples</h1>

        <section style={{marginBottom: 40}}>
          <h2>Basic Magic Button + Tooltip</h2>
          <BasicMagicExample />
        </section>

        <section style={{marginBottom: 40}}>
          <h2>Text Revision</h2>
          <RevisionExample />
        </section>

        <section style={{marginBottom: 40}}>
          <h2>Direct Hook Usage</h2>
          <DirectHookExample />
        </section>
      </div>
    </ChatClientProvider>
  );
}
