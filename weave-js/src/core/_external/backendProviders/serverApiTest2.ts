import * as String from '@wandb/weave/common/util/string';
import {
  type DirMetadata,
  type FileMetadata,
  MetadataNode,
  ServerAPI,
} from '@wandb/weave/core';
import * as _ from 'lodash';

import * as Vega3 from '../util/vega3';

export const DB = {
  viewer: {
    userId: 0,
  },
  projects: [
    {
      id: 0,
      entityName: 'shawn',
      name: 'fasion-sweep',
      createdAt: '2019-03-01T02:44:20',
      stars: 14,
    },
    {
      id: 1,
      entityName: 'shawn',
      name: 'dsviz_demo',
      createdAt: '2020-01-01T02:44:20',
      stars: 5,
    },
    {
      id: 2,
      entityName: 'shawn',
      name: 'many_tables',
      createdAt: '2020-01-01T02:44:20',
      stars: 5,
    },
  ],
  orgs: [
    {
      id: 0,
      name: 'wandb',
      createdAt: 'jan 1, 2020',
      stars: 14,
    },
  ],
  users: [
    {
      id: 0,
      username: 'shawn',
      name: 'Shawn Weights',
      orgId: 0,
    },
    {
      id: 1,
      username: 'cvp',
      name: 'Chris And',
      orgId: 0,
    },
    {
      id: 2,
      username: 'lukas',
      name: 'Lukas Biases',
      orgId: 0,
    },
  ],
  runs: [
    {
      id: 0,
      projectId: 0,
      userId: 0,
      displayName: 'george',
      createdAt: 'jan 1, 2020',
      stars: 8,
      summary: {
        x: 100,
        y: 101,
      } as {[key: string]: number},
    },
    {
      id: 1,
      projectId: 0,
      userId: 1,
      displayName: 'frank',
      createdAt: 'jan 2, 2020',
      stars: 7,
      summary: {
        x: -10.2,
        y: -1000,
        z: {a: 'hello', b: 99.1},
        table: {
          artifact_path: `wandb-artifact://41727469666163743a32303037353933/train_iou_score_table.table.json`,
          path: 'media/table/dataset_2_ebfb7bf0.table.json',
          size: 4687,
          _type: 'table-file',
          ncols: 3,
        },
        joinedTable: {
          _type: 'joined-table',
          artifact_path: `wandb-artifact://41727469666163743a32303037353933/train-results.joined-table.json`,
        },
        partitionedTable: {
          _type: 'partitioned-table',
          artifact_path: `wandb-artifact://41727469666163743a32303037353933/part_table.partitioned-table.json`,
        },
      } as {[key: string]: any},
    },
    {
      id: 2,
      projectId: 1,
      userId: 2,
      displayName: 'sally',
      createdAt: 'jan 3, 2020',
      stars: 5,
      summary: {
        x: 10.1,
        y: 6,
      } as {[key: string]: number},
    },
    {
      id: 3,
      projectId: 1,
      userId: 0,
      displayName: 'bob',
      createdAt: 'nov 8, 2019',
      stars: 1,
      summary: {
        x: 5,
        y: 6.1,
      } as {[key: string]: number},
    },
    {
      id: 4,
      projectId: 2,
      userId: 1,
      displayName: 'many-tables-1',
      createdAt: 'nov 8, 2019',
      stars: 1,
      summary: {
        x: 5,
        y: 6.1,
      } as {[key: string]: number},
    },
  ],
  artifactTypes: [
    {
      id: 0,
      projectId: 1,
      name: 'dataset',
    },
    {
      id: 1,
      projectId: 2,
      name: 'dataset',
    },
  ],
  artifacts: [
    {
      id: 0,
      name: 'train_results',
    },
    {
      id: 1,
      name: 'tables',
    },
  ],
  artifactVersions: [
    {
      id: 0,
      projectId: 1,
      artifactTypeId: 0,
      artifactId: 0,
      aliases: [
        {
          alias: 'v2',
        },
      ],
      versionIndex: 2,
      outputByRunId: 1,
      inputToRunIds: [2],
      createdAt: 'jan 9, 2020',
      stars: 2,
      size: 1921,
    },
    {
      id: 1,
      projectId: 1,
      outputByRunId: 1,
      artifactTypeId: 0,
      artifactId: 0,
      aliases: [
        {
          alias: 'v3',
        },
      ],
      versionIndex: 3,
      inputToRunIds: [3],
      createdAt: 'jan 8, 2020',
      stars: 5,
      size: 1921,
    },
    {
      id: 2,
      projectId: 2,
      outputByRunId: 4,
      artifactTypeId: 1,
      artifactId: 1,
      aliases: [
        {
          alias: 'v0',
        },
      ],
      versionIndex: 0,
      inputToRunIds: [],
      createdAt: 'jan 8, 2020',
      stars: 5,
      size: 4555,
    },
    {
      id: 3,
      projectId: 2,
      outputByRunId: 4,
      artifactTypeId: 1,
      artifactId: 1,
      aliases: [
        {
          alias: 'v1',
        },
      ],
      versionIndex: 1,
      inputToRunIds: [],
      createdAt: 'jan 8, 2020',
      stars: 5,
      size: 9999,
    },
    {
      id: 4,
      projectId: 2,
      outputByRunId: 4,
      artifactTypeId: 1,
      artifactId: 1,
      aliases: [
        {
          alias: 'v2',
        },
      ],
      versionIndex: 2,
      inputToRunIds: [],
      createdAt: 'jan 8, 2020',
      stars: 5,
      size: 191515,
    },
    {
      id: 5,
      projectId: 2,
      outputByRunId: 4,
      artifactTypeId: 1,
      artifactId: 1,
      aliases: [
        {
          alias: 'v3',
        },
      ],
      versionIndex: 3,
      inputToRunIds: [],
      createdAt: 'jan 8, 2020',
      stars: 5,
      size: 2,
    },
    {
      id: 6,
      projectId: 2,
      outputByRunId: 4,
      artifactTypeId: 1,
      artifactId: 1,
      aliases: [
        {
          alias: 'v4',
        },
      ],
      versionIndex: 4,
      inputToRunIds: [],
      createdAt: 'jan 8, 2020',
      stars: 5,
      size: 2,
    },
  ],
};

const CROSS_ARTIFACT_FILES: {
  [artifactId: string]:
    | undefined
    | {[path: string]: {artifactId: string; path: string}};
} = {
  5: {
    'remote_media_table.table.json': {
      artifactId: '3',
      path: 'media_table.table.json',
    },
  },
};

const RUN_FILES: {
  [entityName: string]: {
    [projectName: string]: {
      [runName: string]: {
        [fileName: string]: string | null;
      };
    };
  };
} = {};

const FILES: {
  [artifactId: string]: undefined | {[path: string]: string | undefined};
} = {
  0: {
    'raw_examples.table.json': JSON.stringify({
      columns: ['a', 'b', 'x', 'j'],
      data: [
        [14, -2, 'dog', 'j1'],
        [1, 21, 'dog', 'j2'],
        [9, 24, 'roar', 'j3'],
      ],
    }),
    'groupby_examples.table.json': JSON.stringify({
      columns: ['id', 'species', 'napSpot'],
      data: [
        [1, 'dog', 'couch'],
        [7, 'narwhal', 'under the sea'],
        [2, 'dog', 'bed'],
        [3, 'dog', 'bed'],
        [4, 'cat', 'couch'],
        [5, 'cat', 'windowsill'],
        [6, 'cat', 'couch'],
      ],
    }),
    'train_iou_score_table.table.json': JSON.stringify({
      columns: ['a', 'b', 'x'],
      data: [
        [14, -1, 'cat'],
        [14, -1, 'cat'],
        [14, -2, 'dog'],
        [1, 2, 'dog'],
        [9, 2, 'dog'],
      ],
    }),
    'train-results.joined-table.json': JSON.stringify({
      _type: 'joined-table',
      join_key: 'a',
      table1: 'train_iou_score_table.table.json',
      table2: 'raw_examples.table.json',
    }),
    'part_table.partitioned-table.json': JSON.stringify({
      _type: 'partitioned-table',
      parts_path: 'parts',
    }),
    'parts/t1.table.json': JSON.stringify({
      columns: ['a', 'b', 'c'],
      data: [
        [1, 'a', true],
        [2, 'b', false],
        [3, 'c', true],
      ],
    }),
    'parts/t2.table.json': JSON.stringify({
      columns: ['a', 'b', 'c'],
      data: [
        [4, 'd', true],
        [5, 'e', false],
        [6, 'f', true],
      ],
    }),
    'parts/t3.table.json': JSON.stringify({
      columns: ['a', 'b', 'c'],
      data: [
        [7, 'g', true],
        [8, 'h', false],
        [9, 'i', true],
      ],
    }),
  },
  // Note for the summary test, which uses a real graphql artifact ID, we
  // put a special entry here. We should switch everything in this file
  // to use real graphql IDs
  'QXJ0aWZhY3Q6MjAwNzU5Mw==': {
    'raw_examples.table.json': JSON.stringify({
      columns: ['a', 'b', 'x', 'j'],
      data: [
        [14, -2, 'dog', 'j1'],
        [1, 21, 'dog', 'j2'],
        [9, 24, 'roar', 'j3'],
      ],
    }),
    'train_iou_score_table.table.json': JSON.stringify({
      columns: ['a', 'b', 'x'],
      data: [
        [14, -1, 'cat'],
        [14, -1, 'cat'],
        [14, -2, 'dog'],
        [1, 2, 'dog'],
        [9, 2, 'dog'],
      ],
    }),
    'train-results.joined-table.json': JSON.stringify({
      _type: 'joined-table',
      join_key: 'a',
      table1: 'train_iou_score_table.table.json',
      table2: 'raw_examples.table.json',
    }),
    'part_table.partitioned-table.json': JSON.stringify({
      _type: 'partitioned-table',
      parts_path: 'parts',
    }),
    'parts/t1.table.json': JSON.stringify({
      columns: ['a', 'b', 'c'],
      data: [
        [1, 'a', true],
        [2, 'b', false],
        [3, 'c', true],
      ],
    }),
    'parts/t2.table.json': JSON.stringify({
      columns: ['a', 'b', 'c'],
      data: [
        [4, 'd', true],
        [5, 'e', false],
        [6, 'f', true],
      ],
    }),
    'parts/t3.table.json': JSON.stringify({
      columns: ['a', 'b', 'c'],
      data: [
        [7, 'g', true],
        [8, 'h', false],
        [9, 'i', true],
      ],
    }),
  },
  2: {
    'media_table.table.json': JSON.stringify({
      columns: ['img', 'id', 'str'],
      data: [
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 360,
            path: 'media/images/0.png',
            width: 640,
          },
          0,
          'a',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 360,
            path: 'media/images/1.png',
            width: 640,
          },
          1,
          'a',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 360,
            path: 'media/images/2.png',
            width: 640,
          },
          2,
          'b',
        ],
      ],
    }),
  },
  3: {
    'media_table.table.json': JSON.stringify({
      columns: ['img', 'id', 'str'],
      data: [
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 100,
            path: 'media/images/0.png',
            width: 100,
          },
          0,
          'a',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 100,
            path: 'media/images/1.png',
            width: 100,
          },
          1,
          'b',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 100,
            path: 'media/images/2.png',
            width: 100,
          },
          2,
          'im-hard-to-find',
        ],
      ],
    }),
  },
  4: {
    'media_table.table.json': JSON.stringify({
      columns: ['img', 'id', 'str'],
      data: [
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/0.png',
            width: 100,
          },
          0,
          'a',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/1.png',
            width: 200,
          },
          1,
          'b',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/2.png',
            width: 100,
          },
          2,
          'b',
        ],
      ],
    }),
  },
  5: {
    'media_table.table.json': JSON.stringify({
      columns: ['img', 'id', 'str'],
      data: [
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/0.png',
            width: 200,
          },
          0,
          'a',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/1.png',
            width: 200,
          },
          1,
          'b',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/2.png',
            width: 200,
          },
          2,
          'b',
        ],
      ],
    }),
    'linked_table.table.json': JSON.stringify({
      column_types: {
        params: {
          type_map: {
            score: {
              wb_type: 'number',
            },
            media_row: {
              params: {
                table: 'remote_media_table.table.json',
              },
              wb_type: 'wandb.TableForeignIndex',
            },
          },
        },
        wb_type: 'dictionary',
      },
      columns: ['media_row', 'score'],
      data: [
        [2, 14.1],
        [0, 23.5],
        [1, 7.1],
      ],
    }),
  },
  6: {
    'media_table.table.json': JSON.stringify({
      columns: ['img', 'id', 'str', 'an-extra-col'],
      data: [
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/0.png',
            width: 200,
          },
          0,
          'a',
          'hello',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/1.png',
            width: 200,
          },
          1,
          'b',
          'im',
        ],
        [
          {
            _type: 'image-file',
            format: 'png',
            height: 200,
            path: 'media/images/2.png',
            width: 200,
          },
          2,
          'b',
          'extra',
        ],
      ],
    }),
  },
};

const FILE_METADATA: {
  [artifactId: string]: {[path: string]: MetadataNode};
} = {
  0: {
    'train_iou_score_table.table.json': {
      type: 'file',
      fullPath: 'train_iou_score_table.table.json',
      url: 'url:artifact0_TEST',
      size: 45,
    },
    'groupby_examples.table.json': {
      type: 'file',
      fullPath: 'groupby_examples.table.json',
      url: 'url:artifact0_TEST',
      size: 45,
    },
    'part_table.partitioned-table.json': {
      type: 'file',
      fullPath: 'part_table.partitioned-table.json',
      url: 'url:artifact0_TEST',
      size: 45,
    },
    'train-results.joined-table.json': {
      type: 'file',
      fullPath: 'train-results.joined-table.json',
      url: 'url:artifact1_TEST2',
      size: 102,
    },
    'raw_examples.table.json': {
      type: 'file',
      fullPath: 'raw_examples.table.json',
      url: 'url:artifact1_TEST3',
      size: 999,
    },
    'parts/t1.table.json': {
      type: 'file',
      fullPath: 'parts/t1.table.json',
      url: 'url:artifact0_TEST',
      size: 99,
    },
    'parts/t2.table.json': {
      type: 'file',
      fullPath: 'parts/t2.table.json',
      url: 'url:artifact0_TEST',
      size: 99,
    },

    'parts/t3.table.json': {
      type: 'file',
      fullPath: 'parts/t3.table.json',
      url: 'url:artifact0_TEST',
      size: 99,
    },
    // TODO: This is all duplicated, could clean up
    '': {
      type: 'dir',
      fullPath: 'parts',
      size: 99,
      dirs: {},
      files: {
        't1.table.json': {
          type: 'file',
          fullPath: 'parts/t1.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },
        't2.table.json': {
          type: 'file',
          fullPath: 'parts/t2.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },

        't3.table.json': {
          type: 'file',
          fullPath: 'parts/t3.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },
      },
    },
    parts: {
      type: 'dir',
      fullPath: 'parts',
      size: 99,
      dirs: {},
      files: {
        't1.table.json': {
          type: 'file',
          fullPath: 'parts/t1.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },
        't2.table.json': {
          type: 'file',
          fullPath: 'parts/t2.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },

        't3.table.json': {
          type: 'file',
          fullPath: 'parts/t3.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },
      },
    },
  },
  'QXJ0aWZhY3Q6MjAwNzU5Mw==': {
    'train_iou_score_table.table.json': {
      type: 'file',
      fullPath: 'train_iou_score_table.table.json',
      url: 'url:artifact0_TEST',
      size: 45,
    },
    'part_table.partitioned-table.json': {
      type: 'file',
      fullPath: 'part_table.partitioned-table.json',
      url: 'url:artifact0_TEST',
      size: 45,
    },
    'train-results.joined-table.json': {
      type: 'file',
      fullPath: 'train-results.joined-table.json',
      url: 'url:artifact1_TEST2',
      size: 102,
    },
    'raw_examples.table.json': {
      type: 'file',
      fullPath: 'raw_examples.table.json',
      url: 'url:artifact1_TEST3',
      size: 999,
    },
    'parts/t1.table.json': {
      type: 'file',
      fullPath: 'parts/t1.table.json',
      url: 'url:artifact0_TEST',
      size: 99,
    },
    'parts/t2.table.json': {
      type: 'file',
      fullPath: 'parts/t2.table.json',
      url: 'url:artifact0_TEST',
      size: 99,
    },

    'parts/t3.table.json': {
      type: 'file',
      fullPath: 'parts/t3.table.json',
      url: 'url:artifact0_TEST',
      size: 99,
    },
    // TODO: This is all duplicated, could clean up
    '': {
      type: 'dir',
      fullPath: 'parts',
      size: 99,
      dirs: {},
      files: {
        't1.table.json': {
          type: 'file',
          fullPath: 'parts/t1.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },
        't2.table.json': {
          type: 'file',
          fullPath: 'parts/t2.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },

        't3.table.json': {
          type: 'file',
          fullPath: 'parts/t3.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },
      },
    },
    parts: {
      type: 'dir',
      fullPath: 'parts',
      size: 99,
      dirs: {},
      files: {
        't1.table.json': {
          type: 'file',
          fullPath: 'parts/t1.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },
        't2.table.json': {
          type: 'file',
          fullPath: 'parts/t2.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },

        't3.table.json': {
          type: 'file',
          fullPath: 'parts/t3.table.json',
          url: 'url:artifact0_TEST',
          size: 99,
        },
      },
    },
  },
  1: {
    'train_iou_score_table.table.json': {
      type: 'file',
      fullPath: 'train_iou_score_table.table.json',
      url: 'url:artifact1_TEST',
      size: 99,
    },
  },
  2: {
    'media_table.table.json': {
      type: 'file',
      fullPath: 'media_table.table.json',
      url: 'url:artifact2_TEST',
      size: 555,
    },
    'media/images/0.png': {
      type: 'file',
      fullPath: 'media/images/0.png',
      url: 'url:media/images/0.png',
      digest: 'media/images/0.png',
      size: 99,
    },
    'media/images/1.png': {
      type: 'file',
      fullPath: 'media/images/1.png',
      url: 'url:media/images/1.png',
      digest: 'media/images/1.png',
      size: 99,
    },
    'media/images/2.png': {
      type: 'file',
      fullPath: 'media/images/2.png',
      url: 'url:media/images/2.png',
      digest: 'media/images/2.png',
      size: 99,
    },
  },
  3: {
    'media_table.table.json': {
      type: 'file',
      fullPath: 'media_table.table.json',
      url: 'url:artifact2_TEST',
      size: 556,
    },
    'media/images/0.png': {
      type: 'file',
      fullPath: 'media/images/0.png',
      url: 'url:media/images/0.png',
      digest: 'media/images/0.png',
      size: 99,
    },
    'media/images/1.png': {
      type: 'file',
      fullPath: 'media/images/1.png',
      url: 'url:media/images/1.png',
      digest: 'media/images/1.png',
      size: 99,
    },
    'media/images/2.png': {
      type: 'file',
      fullPath: 'media/images/2.png',
      url: 'url:media/images/2.png',
      digest: 'media/images/2.png',
      size: 99,
    },
  },
  4: {
    'media_table.table.json': {
      type: 'file',
      fullPath: 'media_table.table.json',
      url: 'url:artifact2_TEST',
      size: 557,
    },
    'media/images/0.png': {
      type: 'file',
      fullPath: 'media/images/0.png',
      url: 'url:media/images/0.png',
      digest: 'media/images/0.png',
      size: 99,
    },
    'media/images/1.png': {
      type: 'file',
      fullPath: 'media/images/1.png',
      url: 'url:media/images/1.png',
      digest: 'media/images/1.png',
      size: 99,
    },
    'media/images/2.png': {
      type: 'file',
      fullPath: 'media/images/2.png',
      url: 'url:media/images/2.png',
      digest: 'media/images/2.png',
      size: 99,
    },
  },
  5: {
    'media_table.table.json': {
      type: 'file',
      fullPath: 'media_table.table.json',
      url: 'url:artifact2_TEST',
      size: 558,
    },
    'remote_media_table.table.json': {
      type: 'file',
      fullPath: 'media_table.table.json',
      ref: 'xyz',
      url: 'url:artifact2_TEST',
      size: 558,
    },
    'linked_table.table.json': {
      type: 'file',
      fullPath: 'linked_table.table.json',
      url: 'url:artifact2_TEST',
      size: 999,
    },
    'media/images/0.png': {
      type: 'file',
      fullPath: 'media/images/0.png',
      url: 'url:media/images/0.png',
      digest: 'media/images/0.png',
      size: 99,
    },
    'media/images/1.png': {
      type: 'file',
      fullPath: 'media/images/1.png',
      url: 'url:media/images/1.png',
      digest: 'media/images/1.png',
      size: 99,
    },
    'media/images/2.png': {
      type: 'file',
      fullPath: 'media/images/2.png',
      url: 'url:media/images/2.png',
      digest: 'media/images/2.png',
      size: 99,
    },
  },
  6: {
    'media_table.table.json': {
      type: 'file',
      fullPath: 'media_table.table.json',
      url: 'url:artifact2_TEST',
      size: 121,
    },
  },
};

// Todo: Not used in any test yet
const MEMBERSHIP_FILE_METADATA: {
  [artifactId: string]: {[path: string]: MetadataNode};
} = {};

function resolveRootProject(field: Vega3.QueryField) {
  const entityNameArg = field.args?.find(a => a.name === 'entityName')?.value;
  const projectNameArg = field.args?.find(a => a.name === 'name')?.value;
  const project = DB.projects.find(
    p => p.entityName === entityNameArg && p.name === projectNameArg
  );
  if (project == null) {
    return {[field.alias ?? 'project']: null};
  }

  const resultFields: {[key: string]: any} = {};
  for (const childField of field.fields) {
    if (childField.name === 'id') {
      resultFields[childField.alias ?? childField.name] = project.id;
    } else if (childField.name === 'createdAt') {
      resultFields[childField.alias ?? childField.name] = project.createdAt;
    } else if (childField.name === 'name') {
      resultFields[childField.alias ?? childField.name] = project.name;
    } else if (childField.name === 'stars') {
      resultFields[childField.alias ?? childField.name] = project.stars;
    } else if (childField.name === 'run') {
      resultFields[childField.alias ?? childField.name] = resolveProjectRun(
        project,
        childField
      );
    } else if (childField.name === 'runs') {
      resultFields[childField.alias ?? childField.name] = {
        // Get edges.node field
        // TODO: This isn't really right. Doesn't handle asking for other fields
        //   on edges
        edges: resolveProjectRuns(
          project,
          childField,
          childField.fields[0].fields[0]
        ),
      };
    } else if (childField.name === 'artifactType') {
      resultFields[childField.alias ?? childField.name] =
        resolveProjectArtifactType(project, childField);
    } else {
      throw new Error('invalid');
    }
  }
  return {[field.alias ?? 'project']: resultFields};
}

function resolveRootOrg(field: Vega3.QueryField) {
  const orgNameArg = field.args?.find(a => a.name === 'name')?.value;
  const org = DB.orgs.find(o => o.name === orgNameArg);
  if (org == null) {
    return {[field.alias ?? 'organization']: null};
  }

  const resultFields: {[key: string]: any} = {};
  for (const childField of field.fields) {
    if (childField.name === 'id') {
      resultFields[childField.alias ?? childField.name] = org.id;
    } else if (childField.name === 'members') {
      resultFields[childField.alias ?? childField.name] = resolveOrgMembers(
        org,
        childField
      );
    } else {
      throw new Error('invalid');
    }
  }
  return {[field.alias ?? 'organization']: resultFields};
}

function resolveUser(user: (typeof DB.users)[number], field: Vega3.QueryField) {
  const resultFields: {[key: string]: any} = {};
  for (const childField of field.fields) {
    if (childField.name === 'id') {
      resultFields[childField.alias ?? childField.name] = user.id;
    } else if (childField.name === 'username') {
      resultFields[childField.alias ?? childField.name] = user.username;
    } else if (childField.name === 'runs') {
      resultFields[childField.alias ?? childField.name] = resolveUserRuns(
        user,
        childField
      );
    } else if (childField.name === 'teams') {
      // Empty for now!
      resultFields[childField.alias ?? childField.name] = {edges: []};
    } else {
      throw new Error(`invalid child field: ${childField.name}`);
    }
  }
  return resultFields;
}

function resolveOrgMembers(
  org: (typeof DB.orgs)[number],
  field: Vega3.QueryField
) {
  const members = DB.users.filter(u => u.orgId === org.id);
  return members.map(member => {
    const resultFields: {[key: string]: any} = {};
    for (const childField of field.fields) {
      if (childField.name === 'id') {
        resultFields[childField.alias ?? childField.name] = member.id;
      } else if (childField.name === 'username') {
        resultFields[childField.alias ?? childField.name] = member.username;
      } else if (childField.name === 'user') {
        resultFields[childField.alias ?? childField.name] = resolveUser(
          member,
          childField
        );
      } else {
        throw new Error(`invalid child field: ${childField.name}`);
      }
    }
    return resultFields;
  });
}

function resolveUserRuns(
  user: (typeof DB.users)[number],
  field: Vega3.QueryField
) {
  const runs = DB.runs.filter(r => r.userId === user.id);
  const nodes = runs.map(run => {
    // Note: duplicated from resolveProjectRuns
    const resultFields: {[key: string]: any} = {};
    for (const childField of field.fields) {
      if (childField.name === 'id') {
        resultFields[childField.alias ?? childField.name] = run.id;
      } else if (childField.name === 'stars') {
        resultFields[childField.alias ?? childField.name] = run.stars;
      } else if (childField.name === 'createdAt') {
        resultFields[childField.alias ?? childField.name] = run.createdAt;
      } else if (childField.name === 'user') {
        resultFields[childField.alias ?? childField.name] = user;
      } else if (childField.name === 'edges') {
        resultFields[childField.fields[0].alias ?? childField.fields[0].name] =
          resolveRun(
            childField.fields[0], // Should be `node`
            run
          );
      } else {
        throw new Error(`invalid childField: ${childField.name}`);
      }
    }
    return resultFields;
  });
  return {
    edges: nodes.map(node => ({node: node.node})),
  };
}

function resolveProjectRuns(
  project: (typeof DB.projects)[number],
  runsField: Vega3.QueryField,
  nodeField: Vega3.QueryField
) {
  let runs = DB.runs.filter(r => r.projectId === project.id);
  const runsFilterArg = runsField.args?.find(a => a.name === 'filter')?.value;
  if (runsFilterArg != null) {
    runs = _.filter(runs, runsFilterArg);
  }
  return runs.map(run => ({node: resolveRun(nodeField, run)}));
}

function resolveRun(
  nodeField: Vega3.QueryField,
  run: (typeof DB.runs)[number]
) {
  const resultFields: {[key: string]: any} = {};
  for (const childField of nodeField.fields) {
    if (childField.name === 'id') {
      resultFields[childField.alias ?? childField.name] = run.id;
    } else if (childField.name === 'displayName') {
      resultFields[childField.alias ?? childField.name] = run.displayName;
    } else if (childField.name === 'summaryMetrics') {
      const keys = childField.args?.find(a => a.name === 'keys')?.value;
      if (keys == null) {
        resultFields[childField.alias ?? childField.name] = JSON.stringify(
          run.summary
        );
      } else {
        const key0 = keys[0];
        resultFields[childField.alias ?? childField.name] = JSON.stringify({
          [key0]: run.summary[key0],
        });
      }
    } else if (childField.name === 'stars') {
      resultFields[childField.alias ?? childField.name] = run.stars;
    } else if (childField.name === 'outputArtifacts') {
      resultFields[childField.alias ?? childField.name] = {
        // Get edges.node field
        // TODO: This isn't really right. Doesn't handle asking for other fields
        //   on edges
        edges: resolveRunOutputArtifacts(run, childField.fields[0].fields[0]),
      };
    } else if (childField.name === 'name') {
      resultFields[childField.alias ?? childField.name] = run.id;
    } else if (childField.name === 'createdAt') {
      resultFields[childField.alias ?? childField.name] = run.createdAt;
    } else if (childField.name === 'user') {
      resultFields[childField.alias ?? childField.name] = DB.users.find(
        u => u.id === run.userId
      );
    } else {
      throw new Error('invalid childField: ' + childField.name);
    }
  }
  return resultFields;
}

function resolveProjectRun(
  project: (typeof DB.projects)[number],
  runField: Vega3.QueryField
) {
  const runNameArg = runField.args?.find(a => a.name === 'name')?.value;
  if (runNameArg == null) {
    throw new Error('invalid');
  }
  const run = DB.runs.find(r => r.id === parseInt(runNameArg, 10));
  if (run == null) {
    return run;
  }
  return resolveRun(runField, run);
}

function resolveProjectArtifactType(
  project: (typeof DB.projects)[number],
  artifactTypeField: Vega3.QueryField
) {
  const nameArg = artifactTypeField.args?.find(a => a.name === 'name')?.value;
  const artifactType = DB.artifactTypes.find(
    at => at.projectId === project.id && at.name === nameArg
  );
  if (artifactType == null) {
    return undefined;
  }
  const resultFields: {[key: string]: any} = {};
  for (const childField of artifactTypeField.fields) {
    if (childField.name === 'id') {
      resultFields[childField.alias ?? childField.name] = artifactType.id;
    } else if (childField.name === 'artifact') {
      resultFields[childField.alias ?? childField.name] =
        resolveArtifactTypeArtifact(artifactType, childField);
    } else {
      throw new Error(
        'invalid childField for projectArtifactType: ' + childField.name
      );
    }
  }
  return resultFields;
}

function artifactNameMatch(
  av: (typeof DB.artifactVersions)[number],
  name: string
) {
  const [artifactName, version] = String.splitOnce(name, ':');
  if (version == null) {
    // I think the server might actually handle this case
    throw new Error('invalid');
  }
  const artifact = DB.artifacts.find(a => a.name === artifactName);
  if (artifact == null) {
    throw new Error('invalid');
  }
  return (
    av.artifactId === artifact.id &&
    version.slice(1) === av.versionIndex.toString()
  );
}

function resolveArtifactTypeArtifact(
  artifactType: (typeof DB.artifactTypes)[number],
  artifactTypeField: Vega3.QueryField
) {
  const artifactNameArg = artifactTypeField.args?.find(
    a => a.name === 'name'
  )?.value;
  const artifactVersion = DB.artifactVersions.find(
    av =>
      av.artifactTypeId === artifactType.id &&
      artifactNameMatch(av, artifactNameArg)
  );
  if (artifactVersion == null) {
    return undefined;
  }
  return resolveArtifact(artifactTypeField, artifactVersion);
}

function resolveArtifact(
  artifactField: Vega3.QueryField,
  artifactVersion: (typeof DB.artifactVersions)[number]
) {
  const resultFields: {[key: string]: any} = {};
  for (const childField of artifactField.fields) {
    if (childField.name === 'id') {
      resultFields[childField.alias ?? childField.name] = artifactVersion.id;
    } else if (childField.name === 'size') {
      resultFields[childField.alias ?? childField.name] = artifactVersion.size;
    } else if (childField.name === 'versionIndex') {
      resultFields[childField.alias ?? childField.name] =
        artifactVersion.versionIndex;
    } else if (childField.name === 'aliases') {
      resultFields[childField.alias ?? childField.name] =
        artifactVersion.aliases;
    } else if (childField.name === 'artifactSequence') {
      const artifactSequence = DB.artifacts.find(
        a => a.id === artifactVersion.artifactId
      );
      if (artifactSequence == null) {
        throw new Error('invalid');
      }
      resultFields[childField.alias ?? childField.name] =
        resolveArtifactSequence(childField, artifactSequence);
    } else {
      throw new Error('invalid childField for Artifact: ' + childField.name);
    }
  }
  return resultFields;
}

function resolveArtifactSequence(
  artifactSequenceField: Vega3.QueryField,
  artifactSequence: (typeof DB.artifacts)[number]
) {
  const resultFields: {[key: string]: any} = {};
  for (const childField of artifactSequenceField.fields) {
    if (childField.name === 'id') {
      resultFields[childField.alias ?? childField.name] = artifactSequence.id;
    } else if (childField.name === 'name') {
      resultFields[childField.alias ?? childField.name] = artifactSequence.name;
    } else {
      throw new Error('invalid childField for Artifact: ' + childField.name);
    }
  }
  return resultFields;
}

function resolveRunOutputArtifacts(
  run: (typeof DB.runs)[number],
  artifactField: Vega3.QueryField
) {
  const artifacts = DB.artifactVersions.filter(a => a.outputByRunId === run.id);
  // Get edges.node field
  // TODO: This isn't really right. Doesn't handle asking for other fields
  //   on edges
  return artifacts.map(a => ({node: resolveArtifact(artifactField, a)}));
}

export class Client implements ServerAPI {
  async execute(query: Vega3.Query): Promise<any> {
    // console.log('EXECUTING QUERY', JSON.stringify(query, undefined, 2));
    if (query.queryFields.length !== 1) {
      throw new Error('invalid');
    }
    const qf0 = query.queryFields[0];
    if (qf0.name === 'project') {
      return new Promise(resolve => {
        // Delay for testing
        // TODO: Unnecessary
        setTimeout(() => {
          resolve(resolveRootProject(qf0));
        }, 1);
      });
    } else if (qf0.name === 'organization') {
      return new Promise(resolve => {
        // Delay for testing
        // TODO: Unnecessary
        setTimeout(() => {
          resolve(resolveRootOrg(qf0));
        }, 1);
      });
    } else if (qf0.name === 'runs') {
      const projectIdArg = qf0.args?.find(a => a.name === 'projectId')?.value;
      return new Promise(resolve => {
        // Delay for testing
        // TODO: Unnecessary
        setTimeout(() => {
          const runs = DB.runs.filter(r => r.projectId === projectIdArg);
          resolve(runs);
        }, 1);
      });
    } else if (qf0.name === 'artifacts') {
      const projectIdArg = qf0.args?.find(a => a.name === 'projectId')?.value;
      return new Promise(resolve => {
        // Delay for testing
        // TODO: Unnecessary
        setTimeout(() => {
          const avs = DB.artifactVersions.filter(
            r => r.projectId === projectIdArg
          );
          resolve(avs);
        }, 1);
      });
    } else if (qf0.name === 'artifacts-createdBy') {
      const artifactIds = qf0.args?.find(a => a.name === 'artifactIds')?.value;
      return new Promise(resolve => {
        // Delay for testing
        // TODO: Unnecessary
        setTimeout(() => {
          const runIds = DB.artifactVersions
            .filter(av => artifactIds.includes(av.id))
            .map(a => a.outputByRunId);
          const runs = runIds.map(rid => DB.runs.find(r => r.id === rid));
          resolve(runs);
        }, 1);
      });
    } else if (qf0.name === 'viewer') {
      return new Promise(resolve => {
        // Delay for testing
        // TODO: Unnecessary
        setTimeout(() => {
          resolve({viewer: resolveUser(DB.users[DB.viewer.userId], qf0)});
        }, 1);
      });
    }
    throw new Error(`invalid: ${qf0.name}`);
  }

  async resetExecutionCache(): Promise<void> {
    // pass - not implemented in the test harness
    return Promise.resolve();
  }

  getArtifactFileContents(artifactId: string, assetPath: string): any {
    return new Promise(resolve => {
      // Delay for testing
      setTimeout(() => {
        const caFile = CROSS_ARTIFACT_FILES[artifactId]?.[assetPath] ?? null;
        if (caFile != null) {
          const {artifactId: refArtifactId, path} = caFile;
          const contents = FILES[refArtifactId]?.[path] ?? null;
          // TODO any because we're not sending ArtifactPathInfo
          // but I think that can be removed.
          resolve({refFileId: caFile as any, contents});
        } else {
          const contents = FILES[artifactId]?.[assetPath] ?? null;
          resolve({refFileId: null, contents});
        }
      }, 1);
    });
  }

  getRunFileContents(
    projectName: string,
    runName: string,
    fileName: string,
    entityName?: string
  ): any {
    return new Promise(resolve => {
      // Delay for testing
      setTimeout(() => {
        const contents =
          RUN_FILES[entityName ?? '']?.[projectName]?.[runName]?.[fileName] ??
          null;
        resolve({contents});
      }, 1);
    });
  }

  getArtifactFileDirectUrl(artifactId: string, assetPath: string): any {
    return new Promise(resolve => {
      // Delay for testing
      // TODO: Unnecessary
      setTimeout(() => {
        // TODO: not actually loading something
        resolve({refFileId: null, directUrl: ''});
      }, 1);
    });
  }

  // TODO: NOT DONE
  getArtifactFileMetadata(artifactId: string, assetPath: string): any {
    return new Promise(resolve => {
      // Delay for testing
      // TODO: Unnecessary
      setTimeout(() => {
        const metadata = FILE_METADATA?.[artifactId]?.[assetPath];
        if (metadata == null) {
          throw new Error(
            `serverApiTest missing metadata for artifact path ${artifactId} "${assetPath}"`
          );
        }
        resolve(metadata);
        // const contents = FILES?.[artifactId]?.[assetPath] ?? null;
        // resolve({refFileId: null, contents});
      }, 1);
    });
  }

  getArtifactMembershipFileMetadata(
    artifactCollectionMembershipId: string,
    entityName: string,
    projectName: string,
    collectionName: string,
    artifactVersionIndex: string,
    assetPath: string
  ): Promise<DirMetadata | FileMetadata | null> {
    return new Promise(resolve => {
      // Delay for testing
      // TODO: Unnecessary
      setTimeout(() => {
        const metadata =
          MEMBERSHIP_FILE_METADATA?.[artifactCollectionMembershipId]?.[
            assetPath
          ];
        if (metadata == null) {
          throw new Error(
            `serverApiTest missing metadata for artifact membership's artifact path ${artifactCollectionMembershipId} "${assetPath}"`
          );
        }
        resolve(metadata);
        // const contents = FILES?.[artifactId]?.[assetPath] ?? null;
        // resolve({refFileId: null, contents});
      }, 1);
    });
  }
}
