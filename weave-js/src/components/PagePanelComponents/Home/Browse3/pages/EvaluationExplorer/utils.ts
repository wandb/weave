import { EvaluationRow } from './types';

/**
 * Calculate a simple hash digest for a row based on its dataset values.
 * 
 * @param row - The evaluation row to calculate digest for
 * @returns A hexadecimal string representing the row digest
 */
export const calculateRowDigest = (row: any): string => {
  // Create a simple hash from dataset values
  const datasetValues = Object.entries(row.dataset || {})
    .filter(([key]) => key !== 'rowDigest')
    .map(([key, value]) => `${key}:${value}`)
    .join('|');
  
  // Simple hash function for browser
  let hash = 0;
  for (let i = 0; i < datasetValues.length; i++) {
    const char = datasetValues.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16).padStart(8, '0');
};

/**
 * Deep clone a row to ensure all nested objects are properly copied.
 * 
 * @param row - The row to clone
 * @returns A deep copy of the row
 */
export const deepCloneRow = (row: EvaluationRow): EvaluationRow => {
  return {
    ...row,
    dataset: { ...row.dataset },
    output: row.output ? JSON.parse(JSON.stringify(row.output)) : {},
    scores: row.scores ? JSON.parse(JSON.stringify(row.scores)) : {}
  };
};

/**
 * Create an empty row with default structure.
 * 
 * @param id - The unique ID for the row
 * @param datasetColumns - The columns to include in the dataset
 * @returns A new empty row
 */
export const createEmptyRow = (id: string, datasetColumns: string[]): EvaluationRow => {
  const dataset: any = {};
  datasetColumns.forEach(col => {
    dataset[col] = '';
  });
  
  return {
    id,
    dataset,
    output: {},
    scores: {}
  };
}; 