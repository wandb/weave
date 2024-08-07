import {GridColumnGroup} from '@mui/x-data-grid-pro';

import {buildTree} from '../common/tabularListViews/buildTree';

describe(`buildTree`, () => {
  it(`correctly converts`, () => {
    const testCases: Array<{
      params: string[];
      result: GridColumnGroup;
    }> = [
      {
        params: ['a.b.c', 'a.b.d', 'a.e', 'f'],
        result: {
          groupId: '',
          children: [
            {
              groupId: 'a',
              headerName: 'a',
              children: [
                {
                  groupId: 'a.b',
                  headerName: 'b',
                  children: [{field: 'a.b.c'}, {field: 'a.b.d'}],
                },
                {field: 'a.e'},
              ],
            },
            {field: 'f'},
          ],
        },
      },
    ];

    for (const {params, result} of testCases) {
      expect(buildTree(params)).toEqual(result);
    }
  });
});
