import {filterNodes} from './filter';

describe('filterNodes', () => {
  it('finds input vars', () => {
    const res = filterNodes(
      {
        nodeType: 'output',
        type: 'number',
        fromOp: {
          name: 'file-size',
          inputs: {
            file: {
              nodeType: 'var',
              type: {
                type: 'file',
                extension: 'json',
                wbObjectType: {type: 'table', columnTypes: {}},
              },
              varName: 'row',
            },
          },
        },
      },
      n => n.nodeType === 'var'
    );
    expect(res.length).toEqual(1);
    expect(res[0].nodeType === 'var' && res[0].varName === 'row').toBeTruthy();
  });
});
