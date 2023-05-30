import {VisualizationSpec} from 'react-vega';

import {patchWBVegaSpec} from './vegaSpecPatches';

const exampleSpec = {
  $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
  description: 'A simple bar chart',
  data: {
    values: [
      {
        Label: 'A',
        Counter: 55,
        Type: null,
        ID: 'NaN',
        TYPE_ID: 'NaN',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'B',
        Counter: 77,
        Type: null,
        ID: 'NaN',
        TYPE_ID: 'NaN',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'C',
        Counter: 11,
        Type: null,
        ID: 'NaN',
        TYPE_ID: 'NaN',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'A',
        Counter: 20,
        Type: 'Model',
        ID: 8,
        TYPE_ID: 'Model_8.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'B',
        Counter: 30,
        Type: 'Model',
        ID: 8,
        TYPE_ID: 'Model_8.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'C',
        Counter: 40,
        Type: 'Model',
        ID: 8,
        TYPE_ID: 'Model_8.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'A',
        Counter: 15,
        Type: 'Model',
        ID: 6,
        TYPE_ID: 'Model_6.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'B',
        Counter: 18,
        Type: 'Model',
        ID: 6,
        TYPE_ID: 'Model_6.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'C',
        Counter: 20,
        Type: 'Model',
        ID: 6,
        TYPE_ID: 'Model_6.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'A',
        Counter: 135,
        Type: 'Model',
        ID: 5,
        TYPE_ID: 'Model_5.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'B',
        Counter: 182,
        Type: 'Model',
        ID: 5,
        TYPE_ID: 'Model_5.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
      {
        Label: 'C',
        Counter: 203,
        Type: 'Model',
        ID: 5,
        TYPE_ID: 'Model_5.0',
        id: '386e7raf',
        name: 'fine-glade-1',
        _defaultColorIndex1: 0,
        color: 'rgb(51, 141, 216)',
      },
    ],
  },
  transform: [
    {
      calculate:
        "if('TYPE_ID' === ''  || datum['TYPE_ID'] === '', false, true)",
      as: 'grouped',
    },
    {
      calculate:
        "if('TYPE_ID' === ''  || datum['TYPE_ID'] === '', datum.name, datum['TYPE_ID'])",
      as: 'newGroupKeys',
    },
    {
      calculate:
        "if('TYPE_ID' === ''  || datum['TYPE_ID'] === '', datum.color, datum['TYPE_ID'])",
      as: 'color',
    },
    {
      aggregate: [
        {
          op: 'average',
          field: 'Counter',
          as: 'Counter',
        },
      ],
      groupby: ['Label', 'newGroupKeys', 'color', 'grouped'],
    },
  ],
  title: '',
  layer: [
    {
      transform: [
        {
          filter: 'datum.grouped === false',
        },
      ],
      mark: {
        type: 'bar',
        tooltip: {
          content: 'data',
        },
      },
      encoding: {
        x: {
          field: 'Label',
        },
        y: {
          field: 'Counter',
          type: 'quantitative',
        },
        color: {
          type: 'nominal',
          field: 'newGroupKeys',
          scale: {}, // this should be set to null
          legend: {
            title: {},
          },
        },
        xOffset: {
          field: 'newGroupKeys',
        },
        opacity: {
          value: 0.6,
        },
      },
    },
    {
      transform: [
        {
          filter: 'datum.grouped === true',
        },
      ],
      mark: {
        type: 'bar',
        tooltip: {
          content: 'data',
        },
      },
      encoding: {
        x: {
          field: 'Label',
        },
        y: {
          field: 'Counter',
          type: 'quantitative',
        },
        color: {
          field: 'newGroupKeys',
          type: 'nominal',
          scale: null, // this should be left as null
          legend: {
            title: {},
          },
        },
        xOffset: {
          field: 'newGroupKeys',
        },
        opacity: {
          value: 0.6,
        },
      },
    },
  ],
  resolve: {
    scale: {
      color: 'independent',
    },
  },
  autosize: 'fit',
};

describe('test vega spec patching', () => {
  it('test {scale: null} patching', () => {
    expect(patchWBVegaSpec(exampleSpec as VisualizationSpec)).toEqual({
      $schema: 'https://vega.github.io/schema/vega-lite/v4.json',
      description: 'A simple bar chart',
      data: {
        values: [
          {
            Label: 'A',
            Counter: 55,
            Type: null,
            ID: 'NaN',
            TYPE_ID: 'NaN',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'B',
            Counter: 77,
            Type: null,
            ID: 'NaN',
            TYPE_ID: 'NaN',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'C',
            Counter: 11,
            Type: null,
            ID: 'NaN',
            TYPE_ID: 'NaN',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'A',
            Counter: 20,
            Type: 'Model',
            ID: 8,
            TYPE_ID: 'Model_8.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'B',
            Counter: 30,
            Type: 'Model',
            ID: 8,
            TYPE_ID: 'Model_8.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'C',
            Counter: 40,
            Type: 'Model',
            ID: 8,
            TYPE_ID: 'Model_8.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'A',
            Counter: 15,
            Type: 'Model',
            ID: 6,
            TYPE_ID: 'Model_6.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'B',
            Counter: 18,
            Type: 'Model',
            ID: 6,
            TYPE_ID: 'Model_6.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'C',
            Counter: 20,
            Type: 'Model',
            ID: 6,
            TYPE_ID: 'Model_6.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'A',
            Counter: 135,
            Type: 'Model',
            ID: 5,
            TYPE_ID: 'Model_5.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'B',
            Counter: 182,
            Type: 'Model',
            ID: 5,
            TYPE_ID: 'Model_5.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
          {
            Label: 'C',
            Counter: 203,
            Type: 'Model',
            ID: 5,
            TYPE_ID: 'Model_5.0',
            id: '386e7raf',
            name: 'fine-glade-1',
            _defaultColorIndex1: 0,
            color: 'rgb(51, 141, 216)',
          },
        ],
      },
      transform: [
        {
          calculate:
            "if('TYPE_ID' === ''  || datum['TYPE_ID'] === '', false, true)",
          as: 'grouped',
        },
        {
          calculate:
            "if('TYPE_ID' === ''  || datum['TYPE_ID'] === '', datum.name, datum['TYPE_ID'])",
          as: 'newGroupKeys',
        },
        {
          calculate:
            "if('TYPE_ID' === ''  || datum['TYPE_ID'] === '', datum.color, datum['TYPE_ID'])",
          as: 'color',
        },
        {
          aggregate: [
            {
              op: 'average',
              field: 'Counter',
              as: 'Counter',
            },
          ],
          groupby: ['Label', 'newGroupKeys', 'color', 'grouped'],
        },
      ],
      title: '',
      layer: [
        {
          transform: [
            {
              filter: 'datum.grouped === false',
            },
          ],
          mark: {
            type: 'bar',
            tooltip: {
              content: 'data',
            },
          },
          encoding: {
            x: {
              field: 'Label',
            },
            y: {
              field: 'Counter',
              type: 'quantitative',
            },
            color: {
              type: 'nominal',
              field: 'newGroupKeys',
              scale: null, // this should be set to null
              legend: {
                title: {},
              },
            },
            xOffset: {
              field: 'newGroupKeys',
            },
            opacity: {
              value: 0.6,
            },
          },
        },
        {
          transform: [
            {
              filter: 'datum.grouped === true',
            },
          ],
          mark: {
            type: 'bar',
            tooltip: {
              content: 'data',
            },
          },
          encoding: {
            x: {
              field: 'Label',
            },
            y: {
              field: 'Counter',
              type: 'quantitative',
            },
            color: {
              field: 'newGroupKeys',
              type: 'nominal',
              scale: null, // this should be left as null
              legend: {
                title: {},
              },
            },
            xOffset: {
              field: 'newGroupKeys',
            },
            opacity: {
              value: 0.6,
            },
          },
        },
      ],
      resolve: {
        scale: {
          color: 'independent',
        },
      },
      autosize: 'fit',
    });
  });
});
