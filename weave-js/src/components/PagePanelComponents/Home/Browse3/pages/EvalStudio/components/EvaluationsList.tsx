import React, {useEffect, useState} from 'react';

import {useGetTraceServerClientContext} from '../../wfReactInterface/traceServerClientContext';
import {fetchEvaluations} from '../api';
import {useEvalStudio} from '../context';
import {EvaluationDefinition} from '../types';

type EvaluationsListProps = {
  entity: string;
  project: string;
};

export const EvaluationsList: React.FC<EvaluationsListProps> = ({
  entity,
  project,
}) => {
  const [evaluations, setEvaluations] = useState<EvaluationDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const {setSelectedEvaluation, setIsCreatingNewEval, selectedEvaluation} =
    useEvalStudio();

  const getTraceServerClient = useGetTraceServerClientContext();

  useEffect(() => {
    const loadEvaluations = async () => {
      try {
        const client = getTraceServerClient();
        const data = await fetchEvaluations(client, entity, project);
        setEvaluations(data);
      } catch (error) {
        console.error('Failed to fetch evaluations:', error);
        setError('Failed to load evaluations');
      } finally {
        setLoading(false);
      }
    };

    loadEvaluations();
  }, [entity, project, getTraceServerClient]);

  if (loading) {
    return <div style={{padding: '1rem'}}>Loading evaluations...</div>;
  }

  if (error) {
    return <div style={{padding: '1rem', color: 'red'}}>{error}</div>;
  }

  return (
    <div style={{display: 'flex', flexDirection: 'column', height: '100%'}}>
      <div
        style={{
          padding: '1rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid #eee',
        }}>
        <h2 style={{margin: 0, fontSize: '1.2rem'}}>Evaluations</h2>
        <button
          onClick={() => setIsCreatingNewEval(true)}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: '#00A4EF',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}>
          Create New
        </button>
      </div>

      {evaluations.length === 0 ? (
        <div style={{padding: '1rem', textAlign: 'center', color: '#666'}}>
          No evaluations found. Create your first one!
        </div>
      ) : (
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
          }}>
          {evaluations.map(evaluation => (
            <div
              key={evaluation.objectId}
              style={{
                padding: '0.75rem 1rem',
                borderBottom: '1px solid #eee',
                cursor: 'pointer',
                backgroundColor:
                  selectedEvaluation?.objectId === evaluation.objectId
                    ? '#f5f5f5'
                    : hoveredId === evaluation.objectId
                    ? '#f5f5f5'
                    : 'white',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
                transition: 'background-color 0.2s',
              }}
              onMouseEnter={() => setHoveredId(evaluation.objectId)}
              onMouseLeave={() => setHoveredId(null)}
              onClick={() => setSelectedEvaluation(evaluation)}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                <div
                  style={{
                    fontWeight: 500,
                    color: '#333',
                  }}>
                  {evaluation.displayName}
                </div>
                <div
                  style={{
                    fontSize: '0.8rem',
                    color: '#666',
                  }}>
                  {evaluation.createdAt.toLocaleDateString()}
                </div>
              </div>
              <div
                style={{
                  display: 'flex',
                  gap: '1rem',
                  fontSize: '0.9rem',
                  color: '#666',
                }}>
                <div>Dataset: {evaluation.datasetRef}</div>
                <div>Scorers: {evaluation.scorerRefs.length}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
