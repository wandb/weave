import * as _ from 'lodash';

import {hash} from '../../model/graph/editing/hash';
import type {DirMetadata, FileMetadata} from '../../model/types';
// CG imports
import * as Types from '../../model/types';
import * as ServerApi from '../../serverApi';
import * as String from '../../util/string';
// Other _external imports
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
      projectId: 1,
      name: 'train_results',
    },
    {
      id: 1,
      projectId: 2,
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
  repoPlotDataRows: [
    {
      x: 1,
      y: 1,
      repoName: 'pytorch',
      plotName: 'rpt_weekly_users_by_country_by_repo',
    },
    {
      x: 2,
      y: 2,
      repoName: 'pytorch',
      plotName: 'rpt_weekly_users_by_country_by_repo',
    },
    {
      x: 3,
      y: 3,
      repoName: 'pytorch',
      plotName: 'rpt_weekly_users_by_country_by_repo',
    },
    {
      x: 4,
      y: 4,
      repoName: 'pytorch',
      plotName: 'rpt_weekly_users_by_country_by_repo',
    },
    {
      x: 5,
      y: 5,
      repoName: 'pytorch',
      plotName: 'rpt_weekly_users_by_country_by_repo',
    },
    {
      x: 6,
      y: 6,
      repoName: 'tensorflow',
      plotName: 'rpt_weekly_users_by_country_by_repo',
    },
    {
      x: 7,
      y: 7,
      repoName: 'tensorflow',
      plotName: 'users-monthly',
    },
    {
      x: 8,
      y: 8,
      repoName: 'tensorflow',
      plotName: 'users-monthly',
    },
    {
      x: 9,
      y: 9,
      repoName: 'tensorflow',
      plotName: 'users-monthly',
    },
    {
      x: 10,
      y: 10,
      repoName: 'tensorflow',
      plotName: 'users-monthly',
    },
    {
      x: 11,
      y: 11,
      repoName: 'pytorch',
      plotName: 'users-monthly',
    },
  ] as Array<{x: number; y: number; repoName: string; plotName: string}>,
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
  [artifactId: string]: {[path: string]: Types.MetadataNode};
} = {
  0: {
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
  [artifactId: string]: {[path: string]: Types.MetadataNode};
} = {};

type ArgsType = {[key: string]: any};

const toMany = (
  typename: string,
  resolver: (context: any, args: ArgsType) => any[]
) => {
  return {
    edgeType: 'toMany',
    dataType: typename,
    resolver,
  };
};

const toOne = (
  typename: string,
  resolver: (context: any, args: ArgsType) => any
) => {
  return {
    edgeType: 'toOne',
    dataType: typename,
    resolver,
  };
};

const fieldMapping = (fieldName: string) => {
  return {
    edgeType: 'field',
    fieldName,
  };
};

const processor = (resolver: (context: any, args: ArgsType) => any) => {
  return {
    edgeType: 'processor',
    resolver,
  };
};

const schema: any = {
  Query: {
    project: toOne('Project', (context: any, args: ArgsType) => {
      return DB.projects.find(
        p => p.entityName === args.entityName && p.name === args.name
      );
    }),
    org: toOne('Org', (context: any, args: ArgsType) => {
      return DB.orgs.find(o => o.name === args.name);
    }),
  },
  Project: {
    run: toOne('Run', (context: any, args: ArgsType) => {
      return DB.runs.find(
        r => r.projectId === context.id && r.id === parseInt(args.name, 10)
      );
    }),
    runs: toMany('Run', (context: any, args: ArgsType) => {
      return DB.runs.filter(r => r.projectId === context.id);
    }),
    artifactType: toOne('ArtifactType', (context: any, args: ArgsType) => {
      return DB.artifactTypes.find(
        at => at.projectId === context.id && at.name === args.name
      );
    }),
    artifactTypes: toMany('ArtifactType', (context: any, args: ArgsType) => {
      return DB.artifactTypes.filter(at => at.projectId === context.id);
    }),
    artifactCollection: toOne(
      'ArtifactCollection',
      (context: any, args: ArgsType) => {
        return DB.artifacts.find(
          at => at.projectId === context.id && at.name === args.name
        );
      }
    ),
    artifactCollections: toMany(
      'ArtifactCollection',
      (context: any, args: ArgsType) => {
        return DB.artifacts.filter(at => at.projectId === context.id);
      }
    ),
  },
  ArtifactCollection: {
    artifacts: toMany('Artifact', (context: any, args: ArgsType) => {
      return DB.artifactVersions.filter(av => av.artifactId === context.id);
    }),
  },
  Run: {
    name: fieldMapping('id'),
    summaryMetrics: processor((context: any, args: ArgsType) => {
      if (args.keys == null) {
        return JSON.stringify(context.summary);
      } else {
        const key0 = args.keys[0];
        return JSON.stringify({
          [key0]: context.summary[key0],
        });
      }
    }),
    outputArtifacts: toMany('Artifact', (context: any, args: ArgsType) => {
      return DB.artifactVersions.filter(a => a.outputByRunId === context.id);
    }),
  },
  Artifact: {
    artifactSequence: toOne(
      'ArtifactSequence',
      (context: any, args: ArgsType) => {
        return DB.artifacts.find(a => a.id === context.artifactId);
      }
    ),
  },
  ArtifactType: {
    artifact: toOne('Artifact', (context: any, args: ArgsType) => {
      return DB.artifactVersions.find(
        av =>
          av.artifactTypeId === context.id && artifactNameMatch(av, args.name)
      );
    }),
  },
  ArtifactSequence: {},
  Org: {
    members: toMany('User', (context: any, args: ArgsType) => {
      return DB.users.filter(u => u.orgId === context.id);
    }),
  },
};

function generalResolver(field: Vega3.QueryField): {[field: string]: any} {
  return {
    [field.alias ?? field.name]: generalResolverInner(field),
  };
}

function generalResolverInner(
  field: Vega3.QueryField,
  typename = 'Query',
  context: any = null
): null | {[field: string]: any} {
  let data: any = null;
  const schemaType = schema[typename as any];
  if (schemaType == null) {
    console.warn(`serverAPITest.ts needs type def for ${typename}`);
  }
  const schemaField = (schemaType ?? {})[field.name];
  if (schemaField != null) {
    if (schemaField.edgeType === 'field') {
      data = context[schemaField.fieldName];
    } else {
      const maybeData = schemaField.resolver(
        context,
        _.fromPairs((field.args ?? []).map(arg => [arg.name, arg.value]))
      );
      if (maybeData != null) {
        if (schemaField.edgeType === 'processor') {
          data = maybeData;
        } else if (schemaField.edgeType === 'toOne') {
          data = {
            __typename: schemaField.dataType,
            ..._.fromPairs(
              field.fields.map(f => [
                f.alias ?? f.name,
                generalResolverInner(f, schemaField.dataType, maybeData),
              ])
            ),
          };
        } else if (schemaField.edgeType === 'toMany') {
          const fieldDef = field.fields.find(f => f.name === 'edges');
          if (fieldDef != null) {
            const nodeDef = fieldDef.fields.find(f => f.name === 'node');
            if (nodeDef != null) {
              data = {
                edges: maybeData.map((d: any) => ({
                  node: {
                    __typename: schemaField.dataType,
                    ..._.fromPairs(
                      nodeDef.fields.map(f => [
                        f.alias ?? f.name,
                        generalResolverInner(f, schemaField.dataType, d),
                      ])
                    ),
                  },
                })),
              };
            }
          }
        }
      }
    }
  } else if (context != null && context[field.name] != null) {
    data = context[field.name];
  } else {
    console.warn(
      `serverAPITest.ts needs implementation for ${typename}.${field.name}(${field.args})`
    );
  }

  return data;
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

function resolveRootRepoInsightsPlotData(field: Vega3.QueryField) {
  const repoNameArg = field.args?.find(a => a.name === 'repoName')?.value;
  const plotNameArg = field.args?.find(a => a.name === 'plotName')?.value;
  if (repoNameArg == null || plotNameArg == null) {
    throw new Error('invalid');
  }
  const plotData = DB.repoPlotDataRows
    .filter(pd => pd.repoName === repoNameArg && pd.plotName === plotNameArg)
    .map(pd => ({
      node: {row: [new Date(0), pd.x, pd.y.toString(), pd.x.toString()]},
    }));

  const queryName = `repoInsights_${hash(repoNameArg)}_${hash(plotNameArg)}`;
  const retVal = {} as any;
  retVal[queryName] = {
    schema: [
      {
        Name: 'created_week',
        Type: 'TIMESTAMP',
        Repeated: false,
        Required: false,
      },
      {Name: 'user_count', Type: 'INTEGER', Repeated: false, Required: false},
      {Name: 'framework', Type: 'STRING', Repeated: false, Required: false},
      {Name: 'country', Type: 'STRING', Repeated: false, Required: false},
    ],
    edges: plotData,
    isNormalizedUserCount: true,
  };
  return retVal;
}

export class Client implements ServerApi.ServerAPI {
  async execute(query: Vega3.Query): Promise<any> {
    if (query.queryFields.length !== 1) {
      throw new Error('invalid');
    }
    const qf0 = query.queryFields[0];
    if (qf0.name === 'project') {
      return new Promise(resolve => {
        // Delay for testing
        // TODO: Unnecessary
        setTimeout(() => {
          resolve(generalResolver(qf0));
        }, 1);
      });
    } else if (qf0.name === 'organization') {
      return new Promise(resolve => {
        // Delay for testing
        // TODO: Unnecessary
        setTimeout(() => {
          resolve(generalResolver(qf0));
        }, 1);
      });
    } else if (qf0.name === 'repoInsightsPlotData') {
      return new Promise(resolve => {
        // Delay for testing
        setTimeout(() => {
          resolve(resolveRootRepoInsightsPlotData(qf0));
        }, 1);
      });
    }
    throw new Error(`invalid: ${qf0.name}`);
  }

  async resetExecutionCache(): Promise<void> {
    // pass - not implemented in the test harness
    return Promise.resolve();
  }

  getArtifactFileContents(
    artifactId: string,
    assetPath: string
  ): Promise<Types.ArtifactFileContent> {
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
  ): Promise<Types.RunFileContent> {
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

  getArtifactFileDirectUrl(
    artifactId: string,
    assetPath: string
  ): Promise<Types.ArtifactFileDirectUrl> {
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
  getArtifactFileMetadata(
    artifactId: string,
    assetPath: string
  ): Promise<Types.DirMetadata | Types.FileMetadata | null> {
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

  // TODO: NOT DONE
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
