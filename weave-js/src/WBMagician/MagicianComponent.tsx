import React, {FC, useState, useRef, useEffect, useCallback} from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  Avatar,
  Chip,
  Menu,
  MenuItem,
  CircularProgress,
  Fade,
  Divider,
  Tooltip,
  alpha,
} from '@mui/material';
import {
  Send as SendIcon,
  SmartToy as AIIcon,
  Person as PersonIcon,
  Settings as SettingsIcon,
  Code as CodeIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';

import {useMagician} from './Magician';
import {ToolApprovalCard} from './components/ToolApprovalCard';
import type {
  Message,
  StreamingResponse,
  RegisteredContext,
  RegisteredTool,
  ToolCall,
} from './types';

interface MagicianComponentProps {
  projectId?: string;
  height?: string | number;
  placeholder?: string;
}

export const MagicianComponent: FC<MagicianComponentProps> = ({
  projectId,
  height = '600px',
  placeholder = 'Ask me anything... (@ to mention contexts/tools)',
}) => {
  const magician = useMagician();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [showMentions, setShowMentions] = useState(false);
  const [mentionSearch, setMentionSearch] = useState('');
  const [mentionAnchor, setMentionAnchor] = useState<HTMLElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // Get available contexts and tools
  const contexts = magician.getMagician().getState().listContexts({}).contexts;
  const tools = magician.getMagician().getState().listTools({}).tools;

  // Handle @ mentions
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInput(value);

    // Check for @ symbol
    const lastAtIndex = value.lastIndexOf('@');
    if (lastAtIndex !== -1 && lastAtIndex === value.length - 1) {
      setShowMentions(true);
      setMentionSearch('');
      setMentionAnchor(e.currentTarget);
    } else if (lastAtIndex !== -1 && value.slice(lastAtIndex).includes(' ')) {
      setShowMentions(false);
    } else if (lastAtIndex !== -1) {
      setMentionSearch(value.slice(lastAtIndex + 1));
    }
  };

  // Insert mention
  const insertMention = (item: RegisteredContext | RegisteredTool, type: 'context' | 'tool') => {
    const lastAtIndex = input.lastIndexOf('@');
    const newInput = 
      input.slice(0, lastAtIndex) + 
      `@${item.displayName} `;
    setInput(newInput);
    setShowMentions(false);
    inputRef.current?.focus();
  };

  // Send message
  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);
    setStreamingContent('');

    try {
      const response = await magician.respond({
        input: userMessage.content,
        projectId,
        conversationId,
      });

      if (!conversationId) {
        setConversationId(response.conversationId);
      }

      let currentContent = '';
      const pendingToolCalls: ToolCall[] = [];

      // Process stream
      for await (const chunk of response.getStream()) {
        if (chunk.type === 'content') {
          currentContent += chunk.content || '';
          setStreamingContent(currentContent);
        } else if (chunk.type === 'tool_call' && chunk.toolCall) {
          pendingToolCalls.push(chunk.toolCall);
        } else if (chunk.type === 'done') {
          // Finalize the message
          const assistantMessage: Message = {
            id: `msg_${Date.now()}`,
            role: 'assistant',
            content: currentContent,
            timestamp: new Date(),
            metadata: pendingToolCalls.length > 0 ? {
              toolCalls: pendingToolCalls
            } : undefined,
          };
          setMessages(prev => [...prev, assistantMessage]);
          setStreamingContent('');
        } else if (chunk.type === 'error') {
          console.error('Stream error:', chunk.error);
          // Add error message
          const errorMessage: Message = {
            id: `msg_${Date.now()}`,
            role: 'assistant',
            content: 'Sorry, I encountered an error processing your request.',
            timestamp: new Date(),
          };
          setMessages(prev => [...prev, errorMessage]);
          setStreamingContent('');
        }
      }
    } catch (error) {
      console.error('Error sending message:', error);
      // Add error message
      const errorMessage: Message = {
        id: `msg_${Date.now()}`,
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsStreaming(false);
    }
  };

  // Copy message
  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  // Handle tool approval
  const handleToolApprove = async (toolCall: ToolCall, modifiedArgs?: Record<string, any>) => {
    // Update the tool call status in the message
    setMessages(prev => prev.map(msg => {
      if (msg.metadata?.toolCalls?.some(tc => tc.id === toolCall.id)) {
        return {
          ...msg,
          metadata: {
            ...msg.metadata,
            toolCalls: msg.metadata.toolCalls.map(tc => 
              tc.id === toolCall.id 
                ? { ...tc, status: 'executing' as const, arguments: modifiedArgs || tc.arguments }
                : tc
            ),
          },
        };
      }
      return msg;
    }));

    // Execute the tool
    try {
      const result = await magician.getMagician().getState().invokeTool({
        key: toolCall.toolKey,
        arguments: modifiedArgs || toolCall.arguments,
      });

      // Update status to completed
      setMessages(prev => prev.map(msg => {
        if (msg.metadata?.toolCalls?.some(tc => tc.id === toolCall.id)) {
          return {
            ...msg,
            metadata: {
              ...msg.metadata,
              toolCalls: msg.metadata.toolCalls.map(tc => 
                tc.id === toolCall.id 
                  ? { ...tc, status: 'completed' as const, result: result.result }
                  : tc
              ),
            },
          };
        }
        return msg;
      }));
    } catch (error) {
      // Update status to failed
      setMessages(prev => prev.map(msg => {
        if (msg.metadata?.toolCalls?.some(tc => tc.id === toolCall.id)) {
          return {
            ...msg,
            metadata: {
              ...msg.metadata,
              toolCalls: msg.metadata.toolCalls.map(tc => 
                tc.id === toolCall.id 
                  ? { ...tc, status: 'failed' as const, error: error instanceof Error ? error.message : 'Unknown error' }
                  : tc
              ),
            },
          };
        }
        return msg;
      }));
    }
  };

  // Handle tool rejection
  const handleToolReject = (toolCall: ToolCall) => {
    setMessages(prev => prev.map(msg => {
      if (msg.metadata?.toolCalls?.some(tc => tc.id === toolCall.id)) {
        return {
          ...msg,
          metadata: {
            ...msg.metadata,
            toolCalls: msg.metadata.toolCalls.map(tc => 
              tc.id === toolCall.id 
                ? { ...tc, status: 'rejected' as const }
                : tc
            ),
          },
        };
      }
      return msg;
    }));
  };

  // Filter mentions
  const filteredContexts = contexts.filter(c => 
    c.displayName.toLowerCase().includes(mentionSearch.toLowerCase())
  );
  const filteredTools = tools.filter(t => 
    t.displayName.toLowerCase().includes(mentionSearch.toLowerCase())
  );

  return (
    <Paper
      sx={{
        height,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        bgcolor: 'background.default',
        borderRadius: 2,
        border: 1,
        borderColor: 'divider',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 3,
          py: 2,
          borderBottom: 1,
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <AIIcon sx={{ color: 'primary.main' }} />
          <Typography variant="h6" sx={{ fontWeight: 500 }}>
            Magician
          </Typography>
          {conversationId && (
            <Chip
              label="Active Session"
              size="small"
              sx={{ 
                bgcolor: alpha('#4CAF50', 0.1),
                color: '#4CAF50',
                fontWeight: 500,
              }}
            />
          )}
        </Box>
        <IconButton size="small">
          <SettingsIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Messages */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          px: 3,
          py: 2,
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
        }}
      >
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onCopy={copyMessage}
            tools={tools}
            onToolApprove={handleToolApprove}
            onToolReject={handleToolReject}
          />
        ))}
        
        {/* Streaming message */}
        {isStreaming && streamingContent && (
          <MessageBubble
            message={{
              id: 'streaming',
              role: 'assistant',
              content: streamingContent,
              timestamp: new Date(),
            }}
            isStreaming
            onCopy={copyMessage}
          />
        )}
        
        {/* Loading indicator */}
        {isStreaming && !streamingContent && (
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
              <AIIcon sx={{ fontSize: 18 }} />
            </Avatar>
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <CircularProgress size={8} sx={{ color: 'text.secondary' }} />
              <CircularProgress size={8} sx={{ color: 'text.secondary', animationDelay: '0.2s' }} />
              <CircularProgress size={8} sx={{ color: 'text.secondary', animationDelay: '0.4s' }} />
            </Box>
          </Box>
        )}
        
        <div ref={messagesEndRef} />
      </Box>

      {/* Input */}
      <Box
        sx={{
          p: 2,
          borderTop: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
          <TextField
            ref={inputRef}
            fullWidth
            multiline
            maxRows={4}
            value={input}
            onChange={handleInputChange}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={placeholder}
            disabled={isStreaming}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: 3,
                bgcolor: 'background.default',
              },
            }}
          />
          <IconButton
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            sx={{
              bgcolor: 'primary.main',
              color: 'white',
              '&:hover': {
                bgcolor: 'primary.dark',
              },
              '&.Mui-disabled': {
                bgcolor: 'action.disabledBackground',
              },
            }}
          >
            <SendIcon />
          </IconButton>
        </Box>

        {/* Active contexts */}
        {contexts.filter(c => c.autoInclude).length > 0 && (
          <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', mr: 1 }}>
              Active context:
            </Typography>
            {contexts.filter(c => c.autoInclude).map(context => (
              <Chip
                key={context.key}
                label={context.displayName}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.75rem' }}
              />
            ))}
          </Box>
        )}
      </Box>

      {/* Mentions menu */}
      <Menu
        open={showMentions}
        anchorEl={mentionAnchor}
        onClose={() => setShowMentions(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        PaperProps={{
          sx: {
            maxHeight: 300,
            minWidth: 250,
          },
        }}
      >
        {filteredContexts.length > 0 && (
          <>
            <Typography variant="caption" sx={{ px: 2, py: 1, color: 'text.secondary' }}>
              Contexts
            </Typography>
            {filteredContexts.map(context => (
              <MenuItem
                key={context.key}
                onClick={() => insertMention(context, 'context')}
                sx={{ py: 1 }}
              >
                <CodeIcon sx={{ mr: 1.5, fontSize: 18, color: 'text.secondary' }} />
                <Box>
                  <Typography variant="body2">{context.displayName}</Typography>
                  {context.description && (
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      {context.description}
                    </Typography>
                  )}
                </Box>
              </MenuItem>
            ))}
          </>
        )}
        
        {filteredContexts.length > 0 && filteredTools.length > 0 && <Divider />}
        
        {filteredTools.length > 0 && (
          <>
            <Typography variant="caption" sx={{ px: 2, py: 1, color: 'text.secondary' }}>
              Tools
            </Typography>
            {filteredTools.map(tool => (
              <MenuItem
                key={tool.key}
                onClick={() => insertMention(tool, 'tool')}
                sx={{ py: 1 }}
              >
                <CodeIcon sx={{ mr: 1.5, fontSize: 18, color: 'primary.main' }} />
                <Box>
                  <Typography variant="body2">{tool.displayName}</Typography>
                  <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                    {tool.description}
                  </Typography>
                </Box>
              </MenuItem>
            ))}
          </>
        )}
      </Menu>
    </Paper>
  );
};

// Message bubble component
const MessageBubble: FC<{
  message: Message;
  isStreaming?: boolean;
  onCopy: (content: string) => void;
  tools?: RegisteredTool[];
  onToolApprove?: (toolCall: ToolCall, modifiedArgs?: Record<string, any>) => void;
  onToolReject?: (toolCall: ToolCall) => void;
}> = ({ message, isStreaming, onCopy, tools = [], onToolApprove, onToolReject }) => {
  const isUser = message.role === 'user';
  const [showCopy, setShowCopy] = useState(false);
  const toolCalls = message.metadata?.toolCalls || [];

  return (
    <Fade in>
      <Box>
        <Box
          sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}
          onMouseEnter={() => setShowCopy(true)}
          onMouseLeave={() => setShowCopy(false)}
        >
          <Avatar
            sx={{
              width: 32,
              height: 32,
              bgcolor: isUser ? 'grey.400' : 'primary.main',
            }}
          >
            {isUser ? <PersonIcon sx={{ fontSize: 18 }} /> : <AIIcon sx={{ fontSize: 18 }} />}
          </Avatar>
          
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {isUser ? 'You' : 'Magician'}
              </Typography>
              {isStreaming && (
                <Chip
                  label="Streaming"
                  size="small"
                  sx={{
                    height: 16,
                    fontSize: '0.7rem',
                    bgcolor: alpha('#2196F3', 0.1),
                    color: '#2196F3',
                  }}
                />
              )}
            </Box>
            
            <Typography
              variant="body1"
              sx={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                color: isStreaming ? 'text.secondary' : 'text.primary',
              }}
            >
              {message.content}
              {isStreaming && (
                <Box
                  component="span"
                  sx={{
                    display: 'inline-block',
                    width: 8,
                    height: 16,
                    bgcolor: 'primary.main',
                    ml: 0.5,
                    animation: 'blink 1s infinite',
                    '@keyframes blink': {
                      '0%, 50%': { opacity: 1 },
                      '51%, 100%': { opacity: 0 },
                    },
                  }}
                />
              )}
            </Typography>
          </Box>
          
          {showCopy && !isStreaming && (
            <Fade in>
              <Tooltip title="Copy message">
                <IconButton
                  size="small"
                  onClick={() => onCopy(message.content)}
                  sx={{
                    opacity: 0.6,
                    '&:hover': { opacity: 1 },
                  }}
                >
                  <CopyIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Fade>
          )}
        </Box>
        
        {/* Tool calls */}
        {toolCalls.length > 0 && (
          <Box sx={{ mt: 2, ml: 5.5, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {toolCalls.map((toolCall) => {
              const tool = tools.find(t => t.key === toolCall.toolKey);
              if (!tool) return null;
              
              // Only show approval card for pending tools
              if (toolCall.status === 'pending' && !tool.autoExecutable) {
                return (
                  <ToolApprovalCard
                    key={toolCall.id}
                    toolCall={toolCall}
                    tool={tool}
                    onApprove={(modifiedArgs) => onToolApprove?.(toolCall, modifiedArgs)}
                    onReject={() => onToolReject?.(toolCall)}
                  />
                );
              }
              
              // Show status for other states
              if (toolCall.status !== 'pending') {
                return (
                  <Chip
                    key={toolCall.id}
                    label={`${tool.displayName}: ${toolCall.status}`}
                    size="small"
                    color={
                      toolCall.status === 'completed' ? 'success' :
                      toolCall.status === 'failed' ? 'error' :
                      'default'
                    }
                    variant="outlined"
                  />
                );
              }
              
              return null;
            })}
          </Box>
        )}
      </Box>
    </Fade>
  );
};
