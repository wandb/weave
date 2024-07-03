import {Filters} from './types';

export const parseFilters = (filters: string): Filters => {
  try {
    return JSON.parse(filters);
  } catch (e) {
    return [];
  }
};
