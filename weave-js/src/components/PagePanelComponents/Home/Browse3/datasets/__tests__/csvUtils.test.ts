import {analyzeColumns, detectDataType, parseCSV} from '../csvUtils';

describe('detectDataType', () => {
  test('detects null values', () => {
    expect(detectDataType(null)).toBe('null');
    expect(detectDataType(undefined)).toBe('null');
    expect(detectDataType('')).toBe('null');
  });

  test('detects number values', () => {
    expect(detectDataType('123')).toBe('number');
    expect(detectDataType('-123.45')).toBe('number');
    expect(detectDataType('0')).toBe('number');
    expect(detectDataType(123)).toBe('number');
  });

  test('detects boolean values', () => {
    expect(detectDataType('true')).toBe('boolean');
    expect(detectDataType('false')).toBe('boolean');
    expect(detectDataType('TRUE')).toBe('boolean');
    expect(detectDataType('FALSE')).toBe('boolean');
  });

  test('detects date values', () => {
    expect(detectDataType('2024-03-15')).toBe('date');
    expect(detectDataType('03/15/2024')).toBe('date');
    expect(detectDataType('2024-03-15T10:30:00')).toBe('date');
  });

  test('detects string values', () => {
    expect(detectDataType('hello')).toBe('string');
    expect(detectDataType('123abc')).toBe('string');
    expect(detectDataType('not-a-date')).toBe('string');
  });

  test('handles edge cases', () => {
    expect(detectDataType('NaN')).toBe('string');
    expect(detectDataType('Infinity')).toBe('string');
    expect(detectDataType('null')).toBe('string');
    expect(detectDataType('undefined')).toBe('string');
  });
});

describe('analyzeColumns', () => {
  test('handles empty data', () => {
    expect(analyzeColumns([])).toEqual([]);
  });

  test('analyzes simple columns', () => {
    const data = [
      {name: 'John', age: '25', active: 'true'},
      {name: 'Jane', age: '30', active: 'false'},
    ];

    const result = analyzeColumns(data);
    expect(result).toEqual([
      {name: 'name', type: 'string', sample: 'John'},
      {name: 'age', type: 'number', sample: '25'},
      {name: 'active', type: 'boolean', sample: 'true'},
    ]);
  });

  test('handles mixed types in columns', () => {
    const data = [{value: '123'}, {value: 'abc'}, {value: '456'}];

    const result = analyzeColumns(data);
    expect(result).toEqual([
      {name: 'value', type: 'string', sample: '123'}, // Falls back to string
    ]);
  });

  test('handles columns with all null values', () => {
    const data = [{empty: ''}, {empty: null}, {empty: undefined}];

    const result = analyzeColumns(data);
    expect(result).toEqual([{name: 'empty', type: 'null', sample: null}]);
  });

  test('handles date columns', () => {
    const data = [
      {date: '2024-03-15'},
      {date: '2024-03-16'},
      {date: '2024-03-17'},
    ];

    const result = analyzeColumns(data);
    expect(result).toEqual([
      {name: 'date', type: 'date', sample: '2024-03-15'},
    ]);
  });
});

describe('parseCSV', () => {
  // Helper function to create a File object from a string
  const createCSVFile = (content: string): File => {
    return new File([content], 'test.csv', {type: 'text/csv'});
  };

  test('parses basic CSV with headers', async () => {
    const csv = 'name,age\nJohn,25\nJane,30';
    const file = createCSVFile(csv);

    const result = await parseCSV(file);
    expect(result.data).toEqual([
      {name: 'John', age: 25},
      {name: 'Jane', age: 30},
    ]);
    expect(result.errors).toEqual([]);
    expect(result.meta.columns).toEqual([
      {name: 'name', type: 'string', sample: 'John'},
      {name: 'age', type: 'number', sample: '25'},
    ]);
  });

  test('handles CSV with mixed data types', async () => {
    const csv = 'col1,col2,col3\n123,true,2024-03-15\nabc,false,2024-03-16';
    const file = createCSVFile(csv);

    const result = await parseCSV(file);
    expect(result.meta.columns).toEqual([
      {name: 'col1', type: 'string', sample: '123'}, // Mixed types
      {name: 'col2', type: 'boolean', sample: 'true'},
      {name: 'col3', type: 'date', sample: '2024-03-15'},
    ]);
  });

  test('automatically detects different delimiters', async () => {
    // Test with tab delimiter
    const tabCsv = 'name\tage\nJohn\t25\nJane\t30';
    const tabFile = createCSVFile(tabCsv);
    const tabResult = await parseCSV(tabFile);
    expect(tabResult.data).toEqual([
      {name: 'John', age: 25},
      {name: 'Jane', age: 30},
    ]);
    expect(tabResult.meta.delimiter).toBe('\t');

    // Test with semicolon delimiter
    const semicolonCsv = 'name;age\nJohn;25\nJane;30';
    const semicolonFile = createCSVFile(semicolonCsv);
    const semicolonResult = await parseCSV(semicolonFile);
    expect(semicolonResult.data).toEqual([
      {name: 'John', age: 25},
      {name: 'Jane', age: 30},
    ]);
    expect(semicolonResult.meta.delimiter).toBe(';');
  });

  test('handles empty CSV', async () => {
    const csv = 'col1,col2\n';
    const file = createCSVFile(csv);

    const result = await parseCSV(file);
    expect(result.data).toEqual([]);
    expect(result.meta.totalRows).toBe(0);
  });

  test('handles CSV with missing values', async () => {
    const csv = 'name,age,city\nJohn,25,\nJane,,New York';
    const file = createCSVFile(csv);

    const result = await parseCSV(file);
    expect(result.data).toEqual([
      {name: 'John', age: 25, city: null},
      {name: 'Jane', age: null, city: 'New York'},
    ]);
  });

  test('handles CSV with different delimiters', async () => {
    const csv = 'name;age;city\nJohn;25;New York\nJane;30;Boston';
    const file = createCSVFile(csv);

    const result = await parseCSV(file);
    expect(result.meta.delimiter).toBe(';');
    expect(result.data).toEqual([
      {name: 'John', age: 25, city: 'New York'},
      {name: 'Jane', age: 30, city: 'Boston'},
    ]);
  });

  test('handles malformed CSV', async () => {
    const csv = 'col1,col2\n1,2,3\n4,5';
    const file = createCSVFile(csv);

    const result = await parseCSV(file);
    expect(result.errors.length).toBeGreaterThan(0);
  });
});
