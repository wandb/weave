import Input from '@wandb/weave/common/components/Input';
import {IconNames} from '@wandb/weave/components/Icon';
import backendHost from '@wandb/weave/config';
import React, {useMemo, useState} from 'react';
import styled from 'styled-components';

import {Button} from '../../../../../../../Button';
import {Icon} from '../../../../../../../Icon';
import {useWFHooks} from '../../../wfReactInterface/context';
import {TraceCallSchema} from '../../../wfReactInterface/traceServerClientTypes';
import {ThreadViewProps} from '../../types';
import {usePollingCall} from '../../hooks';

const Container = styled.div`
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;

const ScrollContainer = styled.div`
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
`;

const ChatList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const ChatItem = styled.div<{$isSelected?: boolean}>`
  display: flex;
  flex-direction: column;
  gap: 1px;
  border: 1px solid ${props => (props.$isSelected ? '#3B82F6' : '#E2E8F0')};
  border-radius: 6px;
  background: ${props => (props.$isSelected ? '#EFF6FF' : 'white')};
  cursor: pointer;
  transition: all 0.15s ease;
  overflow: hidden;

  &:hover {
    border-color: ${props => (props.$isSelected ? '#3B82F6' : '#94A3B8')};
  }
`;

const Section = styled.div`
  padding: 0;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  position: relative;
`;

const SectionHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8fafc;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid #e2e8f0;

  /* Add shadow when content is scrolled */
  &::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: -1px;
    height: 4px;
    background: linear-gradient(180deg, rgba(0, 0, 0, 0.05), transparent);
    opacity: 0;
    transition: opacity 0.2s;
  }

  &[data-scrolled='true']::after {
    opacity: 1;
  }
`;

const RunningIndicator = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #3B82F6;
  padding: 8px;
  text-align: center;
`;

const Label = styled.div`
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
`;

const ContentWrapper = styled.div`
  padding: 12px;
  padding-top: 0;
`;

const Content = styled.div<{$isExpanded: boolean}>`
  font-size: 13px;
  color: #0f172a;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: ${props => (props.$isExpanded ? 'none' : '100px')};
  overflow-y: auto;
  transition: max-height 0.15s ease;
  position: relative;

  &::-webkit-scrollbar {
    width: 8px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 4px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
  }
`;

const ExpandButton = styled(Button)`
  padding: 2px 6px !important;
  height: auto !important;
  min-height: 0 !important;
`;

const ConnectionPanel = styled.div`
  flex-shrink: 0;
  border-top: 1px solid #e2e8f0;
  padding: 8px 16px;
  background: #f8fafc;
`;

const ConnectionForm = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
`;

const FormSection = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: white;
  margin-top: 8px;
`;

const ChatInput = styled.div`
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
`;

const FormLabel = styled.label`
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
`;

const ErrorMessage = styled.div`
  color: #ef4444;
  font-size: 12px;
  margin-top: 4px;
`;

interface ConnectionStatus {
  isConnected: boolean;
  url: string;
  schema: any;
  error: string | null;
  threadId: string | null;
}

interface FormField {
  name: string;
  type: string;
  description?: string;
  required?: boolean;
}

// Shared components for both views
interface ThreadContentProps {
  loading: boolean;
  error: Error | null;
  traceRoots: TraceCallSchema[];
  selectedTraceId?: string;
  onTraceSelect: (traceId: string) => void;
  pollIntervalMs?: number;
}

const ThreadContent: React.FC<ThreadContentProps> = ({
  loading,
  error,
  traceRoots,
  selectedTraceId,
  onTraceSelect,
}) => {
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-moon-500">Loading traces...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center text-red-500">
        Error: {error.message}
      </div>
    );
  }

  return (
    <ChatList>
      {traceRoots.map(traceRoot => (
        <ChatRow
          key={traceRoot.id}
          traceRootCall={traceRoot}
          selectedTraceId={selectedTraceId}
          onTraceSelect={onTraceSelect}
        />
      ))}
    </ChatList>
  );
};

// Static view for browsing existing threads
export const StaticThreadView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traceRoots,
  selectedTraceId,
  loading,
  error,
}) => {
  return (
    <Container>
      <ScrollContainer>
        <ThreadContent
          loading={loading}
          error={error}
          traceRoots={traceRoots}
          selectedTraceId={selectedTraceId}
          onTraceSelect={onTraceSelect}
        />
      </ScrollContainer>
    </Container>
  );
};

// Connected view with runtime controls
export const ConnectedThreadView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traceRoots,
  selectedTraceId,
  loading,
  error,
  onThreadSelect,
}) => {
  // Connection state
  const [connection, setConnection] = useState<ConnectionStatus>({
    isConnected: false,
    url: 'http://localhost:2323',
    schema: null,
    error: null,
    threadId: null,
  });
  const [formValues, setFormValues] = useState<Record<string, any>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  // Extract form fields from schema
  const formFields = useMemo(() => {
    if (!connection.schema) {
      return [];
    }
    return Object.entries(connection.schema.properties || {})
      .filter(([name]) => name !== 'thread_id') // Exclude thread_id
      .map(([name, def]: [string, any]) => ({
        name,
        type: def.type,
        description: def.description,
        required: (connection.schema.required || []).includes(name),
      }));
  }, [connection.schema]);

  // Check if we have a single string input field
  const isSingleStringInput = useMemo(() => {
    return (
      formFields.length === 1 &&
      formFields[0].type === 'string'
    );
  }, [formFields]);

  // Connect to the local runtime
  const handleConnect = async () => {
    try {
      // Validate URL protocol
      const url = new URL(connection.url);
      const isLocalhost = url.hostname === 'localhost' || url.hostname === '127.0.0.1' || url.hostname === '0.0.0.0';
      
      if (!isLocalhost && url.protocol !== 'https:') {
        throw new Error('HTTPS is required for non-localhost connections');
      }

      // eslint-disable-next-line wandb/no-unprefixed-urls
      const response = await fetch(`${connection.url}/thread/schema`);
      if (!response.ok) {
        throw new Error('Failed to fetch schema');
      }
      const schema = await response.json();

      // Generate a new UUID for the thread
      const threadId = crypto.randomUUID();

      // Set the thread ID as the selected thread
      onTraceSelect('');  // Clear any existing trace selection first
      setFormValues({thread_id: threadId});  // Set form values before connection state
      
      setConnection(prev => ({
        ...prev,
        isConnected: true,
        schema,
        error: null,
        threadId,
      }));

      // Update the parent's thread selection
      if (onThreadSelect) {
        onThreadSelect(threadId);
      }
    } catch (err) {
      setConnection(prev => ({
        ...prev,
        isConnected: false,
        schema: null,
        error: (err as Error).message,
        threadId: null,
      }));
      setFormValues({});
      onTraceSelect('');
      if (onThreadSelect) {
        onThreadSelect('');
      }
    }
  };

  // Disconnect from the runtime
  const handleDisconnect = () => {
    setConnection(prev => ({
      ...prev,
      isConnected: false,
      schema: null,
      error: null,
      threadId: null,
    }));
    setFormValues({});
    onTraceSelect('');
    if (onThreadSelect) {
      onThreadSelect('');
    }
  };

  // Run the thread with current form values
  const handleRun = async () => {
    if (!connection.threadId) return;
    
    // Store the current values
    const currentValues = {...formValues};
    const fieldName = isSingleStringInput ? formFields[0].name : null;
    
    // Clear the form immediately
    if (fieldName) {
      setFormValues({thread_id: connection.threadId, [fieldName]: ''});
    } else {
      setFormValues({thread_id: connection.threadId});
    }
    
    setIsRunning(true);
    setRunError(null);
    try {
      // eslint-disable-next-line wandb/no-unprefixed-urls
      const response = await fetch(`${connection.url}/thread/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...currentValues,
          thread_id: connection.threadId,
        }),
      });
      if (!response.ok) {
        throw new Error('Failed to run thread');
      }
      const result = await response.json();
      console.log('Run result:', result);

      // Trigger an immediate re-poll by re-selecting the current trace
      if (selectedTraceId) {
        onTraceSelect(selectedTraceId);
      }
    } catch (err) {
      setRunError((err as Error).message);
      // Restore the form values on error
      setFormValues(currentValues);
    } finally {
      setIsRunning(false);
    }
  };

  // Create a new thread
  const handleNewThread = () => {
    const threadId = crypto.randomUUID();
    setFormValues({thread_id: threadId});
    if (onThreadSelect) {
      onThreadSelect(threadId);
    }
  };

  // console.log('connection', formValues, formFields, formValues[formFields[0].name] ?? '');
  return (
    <Container>
      {connection.isConnected && (
        <ScrollContainer>
          <ThreadContent
            loading={loading}
            error={error}
            traceRoots={traceRoots}
            selectedTraceId={selectedTraceId}
            onTraceSelect={onTraceSelect}
            pollIntervalMs={connection.isConnected ? 2000 : 0}
          />
        </ScrollContainer>
      )}
      <ConnectionPanel>
        {!connection.isConnected ? (
          <>
            <ConnectionForm>
              <Input
                type="text"
                placeholder="Enter runtime URL"
                value={connection.url}
                onChange={e =>
                  setConnection(prev => ({...prev, url: e.target.value}))
                }
                style={{width: '300px'}}
              />
              <Button
                variant="primary"
                onClick={handleConnect}
                icon={IconNames.LinkAlt}
                disabled={loading}>
                Connect
              </Button>
            </ConnectionForm>
            {connection.error && <ErrorMessage>{connection.error}</ErrorMessage>}
            <div style={{marginTop: '8px', fontSize: '12px', color: '#64748B'}}>
              Note: Use HTTP for localhost connections (e.g., http://localhost:2323). HTTPS is required for all other hosts.
            </div>
          </>
        ) : (
          <div className="flex items-center justify-between">
            {isSingleStringInput ? (
              <ChatInput>
                <Input
                  type="text"
                  placeholder={formFields[0].description || 'Type your message...'}
                  value={formValues[formFields[0].name] ?? ''}
                  onChange={e =>
                    setFormValues(prev => ({
                      ...prev,
                      [formFields[0].name]: e.target.value,
                    }))
                  }
                  onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleRun();
                    }
                  }}
                  style={{flex: 1}}
                />
                <Button
                  variant="primary"
                  onClick={handleRun}
                  disabled={isRunning}
                  icon={isRunning ? IconNames.Loading : IconNames.Play}>
                  {isRunning ? 'Sending...' : 'Send'}
                </Button>
              </ChatInput>
            ) : (
              <FormSection>
                {formFields.map(field => (
                  <div key={field.name}>
                    <FormLabel>
                      {field.name}
                      {field.required && ' *'}
                    </FormLabel>
                    <Input
                      type={field.type === 'number' ? 'number' : 'text'}
                      placeholder={field.description}
                      value={formValues[field.name] ?? ''}
                      onChange={e =>
                        setFormValues(prev => ({
                          ...prev,
                          [field.name]: e.target.value,
                        }))
                      }
                    />
                  </div>
                ))}
                <Button
                  variant="primary"
                  onClick={handleRun}
                  disabled={isRunning}
                  startIcon={isRunning ? IconNames.Loading : IconNames.Play}>
                  {isRunning ? 'Running...' : 'Run'}
                </Button>
              </FormSection>
            )}
            <div className="flex gap-2">
              <Button
                variant="ghost"
                onClick={handleNewThread}
                icon={IconNames.AddNew}
                title="Start new thread">
                New Thread
              </Button>
              <Button
                variant="ghost"
                onClick={handleDisconnect}
                icon={IconNames.Close}
                title="Disconnect">
                Disconnect
              </Button>
            </div>
          </div>
        )}
        {runError && <ErrorMessage>{runError}</ErrorMessage>}
      </ConnectionPanel>
    </Container>
  );
};

function ChatRow({
  traceRootCall,
  selectedTraceId,
  onTraceSelect,
}: {
  traceRootCall: TraceCallSchema;
  selectedTraceId: string | undefined;
  onTraceSelect: (traceId: string) => void;
}) {
  const [isInputExpanded, setIsInputExpanded] = useState(false);
  const [isOutputExpanded, setIsOutputExpanded] = useState(false);
  const [isInputScrolled, setIsInputScrolled] = useState(false);
  const [isOutputScrolled, setIsOutputScrolled] = useState(false);
  const inputContentRef = React.useRef<HTMLDivElement>(null);
  const outputContentRef = React.useRef<HTMLDivElement>(null);

  const handleScroll = (
    event: React.UIEvent<HTMLDivElement>,
    setScrolled: (scrolled: boolean) => void
  ) => {
    const target = event.currentTarget;
    setScrolled(target.scrollTop > 2); // Add small threshold for better UX
  };

  const {loading, result: call} = usePollingCall(
    traceRootCall.project_id.split('/')[0],
    traceRootCall.project_id.split('/')[1],
    traceRootCall.id
  );

  const input = useMemo(() => {
    const rawInput = {...call?.traceCall?.inputs};
    if (rawInput && rawInput.self) {
      delete rawInput.self;
    }
    // Just some hacks for now
    if (rawInput && rawInput.thread_id) {
      delete rawInput.thread_id;
    }
    if (Object.keys(rawInput).length === 1) {
      return rawInput[Object.keys(rawInput)[0]];
    }
    return rawInput;
  }, [call?.traceCall?.inputs]);

  const output = useMemo(() => {
    const rawOutput = call?.traceCall?.output;
    return rawOutput;
  }, [call?.traceCall?.output]);

  const isRunning = !call?.traceCall?.ended_at;

  const handleClick = (e: React.MouseEvent) => {
    // Don't trigger trace selection when clicking expand buttons
    if ((e.target as HTMLElement).closest('button')) {
      e.stopPropagation();
      return;
    }
    onTraceSelect(traceRootCall.trace_id);
  };

  return (
    <ChatItem
      key={traceRootCall.id}
      $isSelected={traceRootCall.trace_id === selectedTraceId}
      onClick={handleClick}>
      <Section>
        <SectionHeader data-scrolled={isInputScrolled}>
          <Label>Input</Label>
          <ExpandButton
            variant="ghost"
            size="small"
            onClick={() => setIsInputExpanded(!isInputExpanded)}
            icon={isInputExpanded ? 'chevron-up' : 'chevron-down'}
          />
        </SectionHeader>
        <ContentWrapper>
          <Content
            ref={inputContentRef}
            $isExpanded={isInputExpanded}
            onScroll={e => handleScroll(e, setIsInputScrolled)}>
            {loading ? 'Loading...' : JSON.stringify(input, null, 2)}
          </Content>
        </ContentWrapper>
      </Section>
      <Section>
        <SectionHeader data-scrolled={isOutputScrolled}>
          <Label>Output</Label>
          <ExpandButton
            variant="ghost"
            size="small"
            onClick={() => setIsOutputExpanded(!isOutputExpanded)}
            icon={isOutputExpanded ? 'chevron-up' : 'chevron-down'}
          />
        </SectionHeader>
        <ContentWrapper>
          {isRunning ? (
            <RunningIndicator>
              <Icon name="loading" className="animate-spin" />
              Running...
            </RunningIndicator>
          ) : (
            <Content
              ref={outputContentRef}
              $isExpanded={isOutputExpanded}
              onScroll={e => handleScroll(e, setIsOutputScrolled)}>
              {loading ? 'Loading...' : JSON.stringify(output, null, 2)}
            </Content>
          )}
        </ContentWrapper>
      </Section>
    </ChatItem>
  );
}
