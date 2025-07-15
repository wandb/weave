/**
 * Example usage of WBMagician2 components
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
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [generatedContent, setGeneratedContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleButtonClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleStream = (content: string, isComplete: boolean) => {
    setGeneratedContent(content);
    if (isComplete) {
      setIsGenerating(false);
      setAnchorEl(null);
    } else if (!isGenerating) {
      setIsGenerating(true);
    }
  };

  const handleError = (error: Error) => {
    console.error('Generation error:', error);
    setIsGenerating(false);
  };

  // Determine button state based on current status
  const getButtonState = () => {
    if (isGenerating) return 'generating';
    if (anchorEl) return 'tooltipOpen';
    return 'default';
  };

  return (
    <div>
      <MagicButton
        onClick={handleButtonClick}
        state={getButtonState()}
        onCancel={() => setAnchorEl(null)}>
        Generate Description
      </MagicButton>

      <MagicTooltip
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleClose}
        onStream={handleStream}
        onError={handleError}
        systemPrompt="You are a helpful assistant that generates clear, concise descriptions."
        placeholder="What would you like me to describe?"
        showModelSelector={true}
      />

      {generatedContent && (
        <div style={{ marginTop: 20, padding: 10, border: '1px solid #ccc' }}>
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
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [originalContent] = useState('The quick brown fox jumps over the lazy dog.');
  const [revisedContent, setRevisedContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const handleStream = (content: string, isComplete: boolean) => {
    setRevisedContent(content);
    if (isComplete) {
      setIsGenerating(false);
      setAnchorEl(null);
    } else if (!isGenerating) {
      setIsGenerating(true);
    }
  };

  return (
    <div>
      <p>Original: {originalContent}</p>
      
      <MagicButton
        onClick={(e) => setAnchorEl(e.currentTarget)}
        state={isGenerating ? 'generating' : anchorEl ? 'tooltipOpen' : 'default'}>
        Revise Text
      </MagicButton>

      <MagicTooltip
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
        onStream={handleStream}
        systemPrompt="You are a helpful assistant that revises text based on user instructions."
        placeholder="How should I revise this text?"
        contentToRevise={originalContent}
      />

      {revisedContent && (
        <p>Revised: {revisedContent}</p>
      )}
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
    <ChatClientProvider value={{ entity: 'my-org', project: 'my-project' }}>
      <div style={{ padding: 20 }}>
        <h1>WBMagician2 Examples</h1>
        
        <section style={{ marginBottom: 40 }}>
          <h2>Basic Magic Button + Tooltip</h2>
          <BasicMagicExample />
        </section>

        <section style={{ marginBottom: 40 }}>
          <h2>Text Revision</h2>
          <RevisionExample />
        </section>

        <section style={{ marginBottom: 40 }}>
          <h2>Direct Hook Usage</h2>
          <DirectHookExample />
        </section>
      </div>
    </ChatClientProvider>
  );
}
