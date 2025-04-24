import {GridFilterModel} from '@mui/x-data-grid-pro';

import {Query} from '../wfReactInterface/traceServerClientInterface/query';

export type Filter = {
  field: string;
  operator: string;
  value: any;
};

export type Filters = Filter[];

// Note: This is the value of an item in the items array of the UI filters value.
// It is not the same as the CallFilter type used for the "filter" param.
export type UIFilter = Filter & {id: number};

// This is the format we store in the URL params.
// It is similar to, but not exactly the same as, the GridFilterModel in Material UI.
export type UIFilters = {
  items: UIFilter[];
  logicOperator: 'and';
};
export const queryToGridFilterModel = (
  query?: Query | null
): GridFilterModel | null => {
  const filters = queryToUiFilters(query);
  if (filters == null) {
    return null;
  }
  return filters as GridFilterModel;
};

export const queryToUiFilters = (query?: Query | null): UIFilters | null => {
  const filters = queryToFilters(query);
  if (filters == null) {
    return null;
  }
  return filtersToUiFilters(filters);
};

const filtersToUiFilters = (filters: Filters): UIFilters => {
  const items: UIFilter[] = filters.map((filter, index) => ({
    ...filter,
    id: index,
  }));
  return {
    items,
    logicOperator: 'and',
  };
};

export const queryToFilters = (query?: Query | null): Filters | null => {
  if (query == null) {
    return null;
  }

  const andOperation = query.$expr.$and;
  if (andOperation) {
    if (andOperation.length === 0) {
      return null;
    }
    return andOperation.map(operandToFilter);
  }

  if (
    query.$expr.$eq ||
    query.$expr.$gt ||
    query.$expr.$gte ||
    query.$expr.$not ||
    query.$expr.$contains
  ) {
    return [operandToFilter(query.$expr)];
  }

  throw new Error(`Could not parse query: ${JSON.stringify(query)}`);
};

const operandToFilter = (operand: any): Filter => {
  if (operand.$eq) {
    return operandToFilterEq(operand);
  }
  if (operand.$contains) {
    return operandToFilterContains(operand);
  }
  if (operand.$gt) {
    return operandToFilterGt(operand);
  }
  if (operand.$gte) {
    return operandToFilterGte(operand);
  }
  if (operand.$not) {
    const filter = operandToFilter(operand.$not[0]);
    if (filter.operator === '(number): >=') {
      filter.operator = '(number): <';
    } else if (filter.operator === '(number): >') {
      filter.operator = '(number): <=';
    } else if (filter.operator === '(number): =') {
      filter.operator = '(number): !=';
    } else if (filter.operator === '(string): equals') {
      filter.operator = '(string): does not equal';
    } else if (filter.operator === '(string): does not equal') {
      filter.operator = '(string): equals';
    } else if (filter.operator === '(any): isEmpty') {
      filter.operator = '(any): isNotEmpty';
    } else if (filter.operator === '(any): isNotEmpty') {
      filter.operator = '(any): isEmpty';
    } else {
      throw new Error(
        `Could not parse not operand: ${JSON.stringify(operand)}`
      );
    }
    return filter;
  }
  if (operand.$or && operand.$or.length > 0) {
    const childFilters = operand.$or.map(operandToFilter);
    if (
      childFilters.every((o: Filter) => o.field === childFilters[0].field) &&
      childFilters.every((o: Filter) => o.operator === '(string): equals')
    ) {
      const operator = '(string): in';
      // TODO: Should we be leaving the values as an array?
      const value = childFilters.map((o: Filter) => o.value).join(',');
      return {field: childFilters[0].field, operator, value};
    }
  }
  throw new Error(`Could not parse operand: ${JSON.stringify(operand)}`);
};

const operandToFilterEq = (operand: any): Filter => {
  let left = operand.$eq[0];
  const right = operand.$eq[1];
  if (left.$convert && ['double', 'int'].includes(left.$convert.to)) {
    left = left.$convert.input;
  }
  if (left.$getField && right.$literal != null) {
    let value = right.$literal;
    if (typeof value === 'string') {
      let operator = '(string): equals';
      if (value === '') {
        operator = '(any): isEmpty';
        value = null;
      }
      const field = left.$getField;
      return {field, operator, value};
    }
    if (typeof value === 'number') {
      const operator = '(number): =';
      const field = left.$getField;
      return {field, operator, value};
    }
  }
  throw new Error(`Could not parse eq operand ${JSON.stringify(operand)}`);
};

const operandToFilterContains = (operand: any): Filter => {
  const {input, substr} = operand.$contains;
  // TODO: Handle case_insensitive correctly
  if (input.$getField && substr.$literal != null) {
    const value = substr.$literal;
    if (typeof value === 'string') {
      const operator = '(string): contains';
      const field = input.$getField;
      return {field, operator, value};
    }
  }
  throw new Error(
    `Could not parse contains operand ${JSON.stringify(operand)}`
  );
};

const operandToFilterGt = (operand: any): Filter => {
  let left = operand.$gt[0];
  const right = operand.$gt[1];
  if (left.$convert && ['double', 'int'].includes(left.$convert.to)) {
    left = left.$convert.input;
  }
  if (left.$getField && right.$literal) {
    const operator = '(number): >';
    const value = right.$literal;
    if (typeof value !== 'number') {
      throw new Error(`Could not parse gt operand: ${JSON.stringify(operand)}`);
    }
    const field = left.$getField;
    return {
      field,
      operator,
      value,
    };
  }
  throw new Error(`Could not parse gt operand: ${JSON.stringify(operand)}`);
};

const operandToFilterGte = (operand: any): Filter => {
  let left = operand.$gte[0];
  const right = operand.$gte[1];
  if (left.$convert && ['double', 'int'].includes(left.$convert.to)) {
    left = left.$convert.input;
  }
  if (left.$getField && right.$literal) {
    const operator = '(number): >=';
    const value = right.$literal;
    if (typeof value !== 'number') {
      throw new Error(
        `Could not parse gte operand: ${JSON.stringify(operand)}`
      );
    }
    const field = left.$getField;
    return {
      field,
      operator,
      value,
    };
  }
  throw new Error(`Could not parse gte operand: ${JSON.stringify(operand)}`);
};
