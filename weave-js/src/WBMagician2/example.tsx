import React, {useState} from 'react';

import {Button} from '../components/Button';
import {MagicFill} from './MagicDialog';
import {MagicButton} from './MagicButton';
import {MagicFillTooltip} from './MagicFillTooltip';

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

/**
 * Example of using MagicButton with MagicFillTooltip for inline AI assistance.
 * This demonstrates the lightweight tooltip mode for quick generations.
 */
export const TooltipModeExample: React.FC = () => {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [content, setContent] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [streamedContent, setStreamedContent] = useState('');

  const handleOpenTooltip = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleCloseTooltip = () => {
    setAnchorEl(null);
    setStreamedContent('');
  };

  const handleStream = (content: string, isComplete: boolean) => {
    setStreamedContent(content);
    if (isComplete) {
      setContent(content);
      setIsGenerating(false);
      setStreamedContent('');
    } else {
      setIsGenerating(true);
    }
  };

  const handleError = (error: Error) => {
    console.error('Generation error:', error);
    setIsGenerating(false);
    // In a real app, show error to user
  };

  const handleCancel = () => {
    setIsGenerating(false);
    handleCloseTooltip();
  };

  return (
    <div className="p-24">
      <h2 className="mb-16 text-lg font-semibold">Inline AI Assistant</h2>
      
      <div className="mb-16">
        <label className="mb-8 block text-sm font-medium">Email Subject</label>
        <div className="flex items-center gap-8">
          <input
            type="text"
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Enter email subject..."
            className="flex-1 rounded-lg border border-moon-250 px-12 py-8"
          />
          <MagicButton
            onClick={handleOpenTooltip}
            isGenerating={isGenerating}
            onCancel={handleCancel}
            iconOnly
            tooltip="Generate with AI"
          />
        </div>
      </div>

      {/* Show streamed content preview while generating */}
      {isGenerating && streamedContent && (
        <div className="mb-16 rounded-lg border border-teal-300/30 bg-teal-50/20 p-12">
          <p className="text-sm text-moon-700">{streamedContent}</p>
        </div>
      )}

      <MagicFillTooltip
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleCloseTooltip}
        onStream={handleStream}
        onError={handleError}
        systemPrompt="You are an expert at writing professional email subject lines. Create clear, concise subject lines that accurately represent the email content."
        placeholder="What's the email about?"
        contentToRevise={content}
      />
    </div>
  );
};

/**
 * Example showing multiple inline AI assistants on a form.
 */
export const FormWithMultipleAssistants: React.FC = () => {
  const [fields, setFields] = useState({
    title: '',
    description: '',
    tags: '',
  });
  const [activeField, setActiveField] = useState<keyof typeof fields | null>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const systemPrompts = {
    title: "You are an expert at creating engaging, SEO-friendly titles. Generate clear, compelling titles.",
    description: "You are an expert copywriter. Create concise, informative descriptions that highlight key points.",
    tags: "You are an expert at categorization. Generate relevant, specific tags separated by commas.",
  };

  const placeholders = {
    title: "What's this about?",
    description: "Key points to cover?",
    tags: "Topic or theme?",
  };

  const handleOpenTooltip = (field: keyof typeof fields, event: React.MouseEvent<HTMLButtonElement>) => {
    setActiveField(field);
    setAnchorEl(event.currentTarget);
  };

  const handleCloseTooltip = () => {
    setAnchorEl(null);
    setActiveField(null);
  };

  const handleStream = (content: string, isComplete: boolean) => {
    if (activeField && isComplete) {
      setFields(prev => ({ ...prev, [activeField]: content }));
      setIsGenerating(false);
      handleCloseTooltip();
    } else {
      setIsGenerating(true);
    }
  };

  return (
    <div className="p-24">
      <h2 className="mb-16 text-lg font-semibold">Product Listing Form</h2>
      
      <div className="space-y-16">
        {(Object.keys(fields) as Array<keyof typeof fields>).map(field => (
          <div key={field}>
            <label className="mb-8 block text-sm font-medium capitalize">{field}</label>
            <div className="flex items-start gap-8">
              {field === 'description' ? (
                <textarea
                  value={fields[field]}
                  onChange={e => setFields(prev => ({ ...prev, [field]: e.target.value }))}
                  placeholder={`Enter ${field}...`}
                  className="h-[80px] flex-1 rounded-lg border border-moon-250 px-12 py-8"
                />
              ) : (
                <input
                  type="text"
                  value={fields[field]}
                  onChange={e => setFields(prev => ({ ...prev, [field]: e.target.value }))}
                  placeholder={`Enter ${field}...`}
                  className="flex-1 rounded-lg border border-moon-250 px-12 py-8"
                />
              )}
              <MagicButton
                onClick={(e: React.MouseEvent<HTMLButtonElement>) => handleOpenTooltip(field, e)}
                isGenerating={isGenerating && activeField === field}
                onCancel={handleCloseTooltip}
                iconOnly
                size="small"
                tooltip={`Generate ${field}`}
              />
            </div>
          </div>
        ))}
      </div>

      {activeField && (
        <MagicFillTooltip
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleCloseTooltip}
          onStream={handleStream}
          onError={(error: Error) => {
            console.error('Generation error:', error);
            setIsGenerating(false);
          }}
          systemPrompt={systemPrompts[activeField]}
          placeholder={placeholders[activeField]}
          contentToRevise={fields[activeField]}
        />
      )}
    </div>
  );
};
