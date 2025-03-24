import classNames from 'classnames';
import React from 'react';
// import * as Plot from '@observablehq/plot';
// import * as d3 from 'd3';
import {useEffect, useRef, useState} from 'react';
import * as vg from '@uwdata/vgplot';
import {parseSpec, astToDOM} from '@uwdata/mosaic-spec';
import {Tailwind} from '../../../../../../Tailwind';

type Data = Record<string, any>;

type TabDashboardProps = {
  entity: string;
  project: string;
  data: Data;
};

export const TabDashboard = ({entity, project, data}: TabDashboardProps) => {
  //   const containerRef = useRef<HTMLDivElement>(null);
  //   //   const [vdata, setVdata] = useState();

  //   const aapl = [
  //     {
  //       Date: new Date('2013-05-13'),
  //       Open: 64.501427,
  //       High: 65.414284,
  //       Low: 64.5,
  //       Close: 64.96286,
  //       Volume: 79237200,
  //     },
  //     {
  //       Date: new Date('2013-05-14'),
  //       Open: 64.835716,
  //       High: 65.028572,
  //       Low: 63.164288,
  //       Close: 63.408573,
  //       Volume: 111779500,
  //     },
  //     {
  //       Date: new Date('2013-05-15'),
  //       Open: 62.737144,
  //       High: 63.0,
  //       Low: 60.337143,
  //       Close: 61.264286,
  //       Volume: 185403400,
  //     },
  //     {
  //       Date: new Date('2013-05-16'),
  //       Open: 60.462856,
  //       High: 62.549999,
  //       Low: 59.842857,
  //       Close: 62.082859,
  //       Volume: 150801000,
  //     },
  //     {
  //       Date: new Date('2013-05-17'),
  //       Open: 62.721428,
  //       High: 62.869999,
  //       Low: 61.572857,
  //       Close: 61.894287,
  //       Volume: 106976100,
  //     },
  //   ];
  //   const vdata = aapl;
  // useEffect(() => {
  //   d3.csv('/gistemp.csv', d3.autoType).then(setData);
  // }, []);

  //   useEffect(() => {
  //     if (vdata === undefined) return;
  //     const plot = Plot.plot({
  //       marks: [Plot.lineY(aapl, {x: 'Date', y: 'Close'})],
  //     });
  //     containerRef.current.append(plot);
  //     return () => plot.remove();
  //   }, [vdata]);
  useEffect(() => {
    vg.coordinator().databaseConnector(vg.wasmConnector());
    vg.coordinator().exec([
      vg.loadObjects('jcr', [
        {foo: 1, bar: 2},
        {foo: 3, bar: 4},
      ]),
    ]);

    // await vg
    //   .coordinator()
    //   .exec([
    //     vg.loadParquet('aapl', 'data/stocks.parquet', {
    //       where: "Symbol = 'AAPL'",
    //     }),
    //   ]);
  }, []);
  const containerRef = useRef<HTMLDivElement>(null);

  const spec = {
    meta: {
      title: 'Bias Parameter',
      description:
        'Dynamically adjust queried values by adding a Param value. The SQL expression is re-computed in the database upon updates.\n',
    },
    // data: {
    //   walk: {
    //     // file: 'data/random-walk.parquet',
    //   },
    // },
    params: {
      point: 0,
    },
    vconcat: [
      {
        input: 'slider',
        label: 'Bias',
        as: '$point',
        min: 0,
        max: 1000,
        step: 1,
      },
      {
        plot: [
          {
            mark: 'areaY',
            data: {
              from: 'jcr',
            },
            x: 'foo',
            y: {
              sql: 'bar + $point',
            },
            fill: 'steelblue',
          },
        ],
        width: 680,
        height: 200,
      },
    ],
  };

  useEffect(() => {
    if (!containerRef.current) return;

    // Clear previous content
    containerRef.current.innerHTML = '';

    // Parse the spec into AST
    const ast = parseSpec(spec);

    // Render AST to the container
    astToDOM(ast).then(dom => {
      console.log({ast, dom});
      containerRef.current.appendChild(dom.element);
    });
    // containerRef.current.appendChild(dom);
  }, [spec]);

  return (
    <Tailwind>
      <div className="flex flex-col sm:flex-row">
        <div className={classNames('mt-4 h-full w-full')}>
          <div id="foo" ref={containerRef} />
        </div>
      </div>
    </Tailwind>
  );
};
