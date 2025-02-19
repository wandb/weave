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
  padding: 16px;
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
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: white;
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
      onTraceSelect('');  // Clear trace selection on error
      if (onThreadSelect) {
        onThreadSelect('');  // Clear thread selection on error
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
    // Clear selections when disconnecting
    onTraceSelect('');
    if (onThreadSelect) {
      onThreadSelect('');
    }
  };

  // Run the thread with current form values
  const handleRun = async () => {
    if (!connection.threadId) return;
    
    setIsRunning(true);
    setRunError(null);
    try {
      // eslint-disable-next-line wandb/no-unprefixed-urls
      const response = await fetch(`${connection.url}/thread/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formValues),
      });
      if (!response.ok) {
        throw new Error('Failed to run thread');
      }
      const result = await response.json();
      console.log('Run result:', result);
    } catch (err) {
      setRunError((err as Error).message);
    } finally {
      setIsRunning(false);
    }
  };

  // Extract form fields from schema
  const formFields = useMemo(() => {
    if (!connection.schema) {
      return [];
    }
    return Object.entries(connection.schema.properties || {}).map(
      ([name, def]: [string, any]) => ({
        name,
        type: def.type,
        description: def.description,
        required: (connection.schema.required || []).includes(name),
      })
    );
  }, [connection.schema]);

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
            onClick={connection.isConnected ? handleDisconnect : handleConnect}
            icon={connection.isConnected ? IconNames.Close : IconNames.LinkAlt}
            disabled={loading}>
            {connection.isConnected ? 'Disconnect' : 'Connect'}
          </Button>
        </ConnectionForm>
        {connection.error && <ErrorMessage>{connection.error}</ErrorMessage>}
        
        {!connection.isConnected && (
          <div style={{marginTop: '8px', fontSize: '12px', color: '#64748B'}}>
            Note: Use HTTP for localhost connections (e.g., http://localhost:2323). HTTPS is required for all other hosts.
          </div>
        )}
        
        {connection.isConnected && formFields.length > 0 && (
          <FormSection>
            <FormLabel>Thread Parameters</FormLabel>
            {formFields.map(field => (
              <div key={field.name}>
                <FormLabel>
                  {field.name}
                  {field.required && ' *'}
                </FormLabel>
                {field.name === 'thread_id' ? (
                  <Input
                    type="text"
                    value={connection.threadId || ''}
                    disabled
                    style={{backgroundColor: '#F1F5F9'}}
                  />
                ) : (
                  <Input
                    type={field.type === 'number' ? 'number' : 'text'}
                    placeholder={field.description}
                    value={formValues[field.name] || ''}
                    onChange={e =>
                      setFormValues(prev => ({
                        ...prev,
                        [field.name]: e.target.value,
                      }))
                    }
                  />
                )}
              </div>
            ))}
            <Button
              variant="primary"
              onClick={handleRun}
              disabled={isRunning}
              startIcon={isRunning ? IconNames.Loading : IconNames.Play}>
              {isRunning ? 'Running...' : 'Run'}
            </Button>
            {runError && <ErrorMessage>{runError}</ErrorMessage>}
          </FormSection>
        )}
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
  const {useCall} = useWFHooks();
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

  const {loading, result: call} = useCall({
    entity: traceRootCall.project_id.split('/')[0],
    project: traceRootCall.project_id.split('/')[1],
    callId: traceRootCall.id,
  });

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
          <Content
            ref={outputContentRef}
            $isExpanded={isOutputExpanded}
            onScroll={e => handleScroll(e, setIsOutputScrolled)}>
            {loading ? 'Loading...' : JSON.stringify(output, null, 2)}
          </Content>
        </ContentWrapper>
      </Section>
    </ChatItem>
  );
}
