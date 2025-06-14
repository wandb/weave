import React, {useState, useMemo} from 'react';
import {Button} from '@wandb/weave/components/Button';
import {MessagePanelPart} from './MessagePanelPart';

interface ThinkingMessageProps {
  content: string;
  isStructuredOutput?: boolean;
  showCursor?: boolean;
}

export const ThinkingMessage: React.FC<ThinkingMessageProps> = ({
  content,
  isStructuredOutput,
  showCursor
}) => {
  const [showThinking, setShowThinking] = useState(false);
  
  // Extract thinking content and regular content
  const {thinkingContent, regularContent} = useMemo(() => {
    // Check for both <think> and <thinking> tags
    const thinkMatch = content.match(/^<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/);
    
    if (!thinkMatch) {
      return {thinkingContent: null, regularContent: content};
    }
    
    const thinking = thinkMatch[1].trim();
    const regular = content.slice(thinkMatch[0].length).trim();
    
    return {
      thinkingContent: thinking,
      regularContent: regular
    };
  }, [content]);
  
  // If no thinking content, render normally
  if (!thinkingContent) {
    return (
      <MessagePanelPart 
        value={content} 
        isStructuredOutput={isStructuredOutput}
        showCursor={showCursor}
      />
    );
  }
  
  return (
    <div>
      <Button
        variant="ghost"
        size="small"
        onClick={() => setShowThinking(!showThinking)}
        className="mb-2 text-xs"
      >
        {showThinking ? 'Hide thinking' : 'Show thinking'}
      </Button>
      
      {showThinking && (
        <div className="mb-4 rounded-lg bg-moon-100 p-4">
          <div className="mb-2 text-xs font-semibold text-moon-600">Model thinking</div>
          <MessagePanelPart 
            value={thinkingContent} 
            isStructuredOutput={false}
            showCursor={false}
          />
        </div>
      )}
      
      {regularContent && (
        <MessagePanelPart 
          value={regularContent} 
          isStructuredOutput={isStructuredOutput}
          showCursor={showCursor && !showThinking}
        />
      )}
    </div>
  );
};