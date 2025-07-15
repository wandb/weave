import React, {useState} from 'react';

import {Button} from '../components/Button';
import {MagicFill} from './MagicDialog';

/**
 * Example component demonstrating how to use MagicFill with full headers.
 * This shows a typical integration pattern for AI-assisted form filling.
 */
export const MagicFillExample: React.FC = () => {
  const [showMagic, setShowMagic] = useState(false);
  const [description, setDescription] = useState('');

  return (
    <div className="p-24">
      <h2 className="mb-16 text-lg font-semibold">Product Description</h2>

      <div className="mb-16">
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="Enter your product description..."
          className="h-[200px] w-full rounded-lg border border-moon-250 p-16"
        />
      </div>

      <Button
        onClick={() => setShowMagic(true)}
        startIcon="magic-wand-star"
        variant="secondary">
        Generate with AI
      </Button>

      <MagicFill
        open={showMagic}
        onClose={() => setShowMagic(false)}
        onAccept={content => {
          setDescription(content);
          setShowMagic(false);
        }}
        title="Generate Product Description"
        details="I'll help you create a compelling product description."
        systemPrompt="You are an expert copywriter specializing in product descriptions. Create engaging, clear, and persuasive descriptions that highlight key features and benefits."
        contentToRevise={description}
        userInstructionPlaceholder="What kind of product would you like to describe? Include any specific features or tone you'd like."
      />
    </div>
  );
};

/**
 * Example of using MagicFill with minimal UI (no title/details).
 * This creates a more compact interface for quick interactions.
 */
export const MinimalMagicFillExample: React.FC = () => {
  const [showMagic, setShowMagic] = useState(false);
  const [code, setCode] = useState('');

  return (
    <div className="p-24">
      <h2 className="mb-16 text-lg font-semibold">Quick Code Generator</h2>

      <div className="mb-16">
        <pre className="h-[150px] overflow-auto rounded-lg bg-moon-900 p-16 text-moon-100">
          <code>{code || '// Your code will appear here'}</code>
        </pre>
      </div>

      <Button
        onClick={() => setShowMagic(true)}
        startIcon="magic-wand-star"
        variant="primary"
        size="small">
        Generate
      </Button>

      <MagicFill
        open={showMagic}
        onClose={() => setShowMagic(false)}
        onAccept={content => {
          setCode(content);
          setShowMagic(false);
        }}
        // No title or details - creates a minimal interface
        systemPrompt="You are an expert programmer. Generate clean, efficient code based on the user's request. Only output the code, no explanations unless specifically asked."
        userInstructionPlaceholder="Describe what code you need..."
        useStreaming={true} // Streaming is enabled by default
      />
    </div>
  );
};

/**
 * Example of using MagicFill for code generation with streaming disabled.
 */
export const CodeGenerationExample: React.FC = () => {
  const [showMagic, setShowMagic] = useState(false);
  const [code, setCode] = useState('');

  return (
    <div className="p-24">
      <h2 className="mb-16 text-lg font-semibold">React Component</h2>

      <div className="mb-16">
        <pre className="h-[300px] overflow-auto rounded-lg bg-moon-900 p-16 text-moon-100">
          <code>{code || '// Your component code will appear here'}</code>
        </pre>
      </div>

      <Button
        onClick={() => setShowMagic(true)}
        startIcon="magic-wand-star"
        variant="primary">
        Generate Component
      </Button>

      <MagicFill
        open={showMagic}
        onClose={() => setShowMagic(false)}
        onAccept={content => {
          setCode(content);
          setShowMagic(false);
        }}
        title="Generate React Component"
        details="I'll help you create a React component with TypeScript."
        systemPrompt="You are an expert React developer. Generate clean, well-documented React components using TypeScript and modern best practices. Include proper types and follow functional component patterns."
        userInstructionPlaceholder="Describe the component you need. What should it do? What props should it accept?"
        useStreaming={false} // Disable streaming for this example
      />
    </div>
  );
};
