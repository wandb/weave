import {getValidFilterModel} from './filters';

describe('getValidFilterModel', () => {
  it('parses valid query values', () => {
    const parsed = getValidFilterModel(
      '{"items":[{"field":"summary.weave.status","operator":"contains","id":71521}],"logicOperator":"and"}'
    );
    expect(parsed).toEqual({
      items: [
        {
          field: 'summary.weave.status',
          operator: 'contains',
          id: 71521,
        },
      ],
      logicOperator: 'and',
    });
  });
});
