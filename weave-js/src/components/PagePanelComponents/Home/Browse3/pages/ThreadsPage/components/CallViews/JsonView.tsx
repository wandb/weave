import JsonView from '@uiw/react-json-view';
import Input from '@wandb/weave/common/components/Input';
import {JSONPath} from 'jsonpath-plus';
import React, {useMemo,useState} from 'react';
import styled from 'styled-components';

import {Button} from '../../../../../../../Button';
import {Icon} from '../../../../../../../Icon';
import {CallViewProps} from '../../types';

const Container = styled.div`
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #f8fafc;
`;

const Controls = styled.div`
  padding: 8px 16px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  gap: 8px;
  align-items: center;
`;

const ScrollContainer = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 16px;

  &::-webkit-scrollbar {
    width: 8px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #CBD5E1;
    border-radius: 4px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #94A3B8;
  }
`;

const FilterError = styled.div`
  color: #ef4444;
  font-size: 12px;
  margin-left: 8px;
`;

const HelpText = styled.div`
  font-size: 12px;
  color: #64748b;
  margin-left: 8px;
`;

export const CallJsonView: React.FC<CallViewProps> = ({call}) => {
  const [filter, setFilter] = useState('');
  const [showHelp, setShowHelp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const data = call.traceCall;

  // Apply JSONPath filter and handle errors
  const filteredData = useMemo(() => {
    if (!filter) { return data; }

    try {
      // Add root selector if not present
      const query = filter.startsWith('$') ? filter : '$' + filter;
      const result = JSONPath({
        path: query,
        json: data,
        wrap: false,
      });
      setError(null);
      return result;
    } catch (err) {
      setError((err as Error).message);
      return data;
    }
  }, [data, filter]);

  const helpExamples = [
    {query: '$.inputs', desc: 'Get all inputs'},
    {query: '$..[?(@.type=="string")]', desc: 'Find all objects with type "string"'},
    {query: '$..id', desc: 'Get all id fields at any level'},
    {query: '$.outputs[*]', desc: 'Get all outputs array elements'},
    {query: '$..[?(@.value>100)]', desc: 'Find objects with value > 100'},
  ];

  return (
    <Container>
      <Controls>
        <Input
          type="text"
          placeholder="Enter JSONPath query... (e.g. $.inputs)"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{width: '400px'}}
        />
        <Button
          variant="ghost"
          icon="info"
          onClick={() => setShowHelp(!showHelp)}
          title="Toggle JSONPath help"
        />
        {error && <FilterError>{error}</FilterError>}
      </Controls>
      {showHelp && (
        <Controls style={{borderTop: '1px solid #e2e8f0'}}>
          <HelpText>
            <div style={{fontWeight: 500, marginBottom: '4px'}}>JSONPath Examples:</div>
            {helpExamples.map((ex, i) => (
              <div key={i} style={{cursor: 'pointer'}} onClick={() => setFilter(ex.query)}>
                <code style={{color: '#3b82f6'}}>{ex.query}</code> - {ex.desc}
              </div>
            ))}
          </HelpText>
        </Controls>
      )}
      <ScrollContainer>
        <JsonView
          value={filteredData}
          style={{backgroundColor: 'transparent'}}
          displayDataTypes={false}
          displayObjectSize={true}
          enableClipboard={true}
          highlightUpdates={true}
          collapsed={1}
          shortenTextAfterLength={120}
          theme={{
            background: 'transparent',
            fontSize: '13px',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            valueColor: '#334155',
            keyColor: '#0f766e',
            borderColor: '#e2e8f0',
            base00: '#f8fafc',
          }}
        />
      </ScrollContainer>
    </Container>
  );
}; 