import {GridColumnGroupingModel} from '@mui/x-data-grid';

import {collapseGroupingModel} from './collapseGroupingModel';

describe('collapseGroupingModel', () => {
  it('should handle empty grouping model', () => {
    const input: GridColumnGroupingModel = [];
    const result = collapseGroupingModel(input);
    expect(result).toEqual([]);
  });

  it('should handle groups with only direct leaf children', () => {
    const input: GridColumnGroupingModel = [
      {
        groupId: 'group1',
        headerName: 'Group 1',
        children: [{field: 'column1'}, {field: 'column2'}],
      },
    ];
    const result = collapseGroupingModel(input);
    expect(result).toEqual(input);
  });

  it('should keep all groups when path length is less than or equal to maxRootGroups + maxLeafGroups', () => {
    const input: GridColumnGroupingModel = [
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B',
            headerName: 'B',
            children: [{field: 'A.B.leaf'}],
          },
        ],
      },
    ];

    const result = collapseGroupingModel(input, 1, 1);
    expect(result).toEqual(input);
  });

  it('should collapse deep nesting keeping only specified root and leaf groups', () => {
    const input: GridColumnGroupingModel = [
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B',
            headerName: 'B',
            children: [
              {
                groupId: 'A.B.C',
                headerName: 'C',
                children: [
                  {
                    groupId: 'A.B.C.D',
                    headerName: 'D',
                    children: [
                      {
                        groupId: 'A.B.C.D.E',
                        headerName: 'E',
                        children: [{field: 'A.B.C.D.E.leaf'}],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ];

    // Keep 1 root group (A) and 1 leaf group (E)
    const result = collapseGroupingModel(input, 1, 1);

    expect(result).toEqual([
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B.C.D.E',
            headerName: 'E',
            children: [{field: 'A.B.C.D.E.leaf'}],
          },
        ],
      },
    ]);
  });

  it('should handle multiple paths from same root', () => {
    const input: GridColumnGroupingModel = [
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B',
            headerName: 'B',
            children: [
              {
                groupId: 'A.B.C',
                headerName: 'C',
                children: [{field: 'A.B.C.leaf1'}],
              },
              {
                groupId: 'A.B.D',
                headerName: 'D',
                children: [{field: 'A.B.D.leaf2'}],
              },
            ],
          },
          {
            groupId: 'A.E',
            headerName: 'E',
            children: [{field: 'A.E.leaf3'}],
          },
        ],
      },
    ];

    // Keep 1 root group and 1 leaf group
    const result = collapseGroupingModel(input, 1, 1);

    expect(result).toEqual([
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B.C',
            headerName: 'C',
            children: [{field: 'A.B.C.leaf1'}],
          },
          {
            groupId: 'A.B.D',
            headerName: 'D',
            children: [{field: 'A.B.D.leaf2'}],
          },
          {
            groupId: 'A.E',
            headerName: 'E',
            children: [{field: 'A.E.leaf3'}],
          },
        ],
      },
    ]);
  });

  it('should handle multiple top-level groups', () => {
    const input: GridColumnGroupingModel = [
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B',
            headerName: 'B',
            children: [
              {
                groupId: 'A.B.C',
                headerName: 'C',
                children: [{field: 'A.B.C.leaf'}],
              },
            ],
          },
        ],
      },
      {
        groupId: 'X',
        headerName: 'X',
        children: [
          {
            groupId: 'X.Y',
            headerName: 'Y',
            children: [
              {
                groupId: 'X.Y.Z',
                headerName: 'Z',
                children: [{field: 'X.Y.Z.leaf'}],
              },
            ],
          },
        ],
      },
    ];

    const result = collapseGroupingModel(input, 1, 1);

    expect(result).toEqual([
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B.C',
            headerName: 'C',
            children: [{field: 'A.B.C.leaf'}],
          },
        ],
      },
      {
        groupId: 'X',
        headerName: 'X',
        children: [
          {
            groupId: 'X.Y.Z',
            headerName: 'Z',
            children: [{field: 'X.Y.Z.leaf'}],
          },
        ],
      },
    ]);
  });

  it('should handle different maxRootGroups and maxLeafGroups values', () => {
    const input: GridColumnGroupingModel = [
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B',
            headerName: 'B',
            children: [
              {
                groupId: 'A.B.C',
                headerName: 'C',
                children: [
                  {
                    groupId: 'A.B.C.D',
                    headerName: 'D',
                    children: [
                      {
                        groupId: 'A.B.C.D.E',
                        headerName: 'E',
                        children: [{field: 'A.B.C.D.E.leaf'}],
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ];

    // Keep 2 root groups (A, B) and 2 leaf groups (D, E)
    const result = collapseGroupingModel(input, 2, 2);

    expect(result).toEqual([
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B',
            headerName: 'B',
            children: [
              {
                groupId: 'A.B.C.D',
                headerName: 'D',
                children: [
                  {
                    groupId: 'A.B.C.D.E',
                    headerName: 'E',
                    children: [{field: 'A.B.C.D.E.leaf'}],
                  },
                ],
              },
            ],
          },
        ],
      },
    ]);
  });

  it('should handle mixed depth paths correctly', () => {
    const input: GridColumnGroupingModel = [
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {field: 'A.shortLeaf'},
          {
            groupId: 'A.B',
            headerName: 'B',
            children: [
              {
                groupId: 'A.B.C',
                headerName: 'C',
                children: [
                  {
                    groupId: 'A.B.C.D',
                    headerName: 'D',
                    children: [{field: 'A.B.C.D.deepLeaf'}],
                  },
                ],
              },
            ],
          },
        ],
      },
    ];

    const result = collapseGroupingModel(input, 1, 1);

    expect(result).toEqual([
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {field: 'A.shortLeaf'},
          {
            groupId: 'A.B.C.D',
            headerName: 'D',
            children: [{field: 'A.B.C.D.deepLeaf'}],
          },
        ],
      },
    ]);
  });

  it('should preserve default values when parameters are not provided', () => {
    const input: GridColumnGroupingModel = [
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B',
            headerName: 'B',
            children: [
              {
                groupId: 'A.B.C',
                headerName: 'C',
                children: [{field: 'A.B.C.leaf'}],
              },
            ],
          },
        ],
      },
    ];

    // Using default values (maxRootGroups=1, maxLeafGroups=1)
    const result = collapseGroupingModel(input);

    expect(result).toEqual([
      {
        groupId: 'A',
        headerName: 'A',
        children: [
          {
            groupId: 'A.B.C',
            headerName: 'C',
            children: [{field: 'A.B.C.leaf'}],
          },
        ],
      },
    ]);
  });
});
