/* tslint:disable */

import {typeToString} from '../../language/js/print';
import {
  constNumberList,
  functionType,
  list,
  maybe,
  taggedValue,
  typedDict,
} from '../../model';
import {constFunction, constNone, constNumber, constString} from '../../model';
import {normalizeType, testClient, testNode} from '../../testUtil';
import {randomlyDownsample} from '../util';
import {
  opJoinAll,
  opJoinAllReturnType,
  opRandomGaussian,
  opRandomlyDownsample,
} from './list';
import {opArray, opDict} from './literals';
import {opPick} from './typedDict';

describe('List Ops', () => {
  it('test opJoinAll - simple', async () => {
    await testNode(
      opJoinAll({
        arrs: opArray({
          0: opArray({
            0: opDict({
              col_a: constNumber(0),
              col_b: constString('hello_0'),
            } as any),
            1: opDict({
              col_a: constNumber(1),
              col_b: constString('world_0'),
            } as any),
          } as any),
          1: opArray({
            0: opDict({
              col_a: constNumber(0),
              col_b: constString('hello_1'),
            } as any) as any,
            1: opDict({
              col_a: constNumber(2),
              col_b: constString('world_1'),
            } as any),
          } as any),
        } as any),
        joinFn: constFunction(
          {
            row: typedDict({
              col_a: 'number',
              col_b: 'string',
            }),
          },
          ({row}) => {
            return opPick({
              obj: row,
              key: constString('col_a'),
            });
          }
        ),
      } as any),
      {
        type: list(
          taggedValue(
            typedDict({joinKey: 'string', joinObj: 'number'}),
            typedDict({
              col_a: list('number'),
              col_b: list('string'),
            })
          )
        ),
        resolvedType: list(
          taggedValue(
            typedDict({joinKey: 'string', joinObj: 'number'}),
            typedDict({
              col_a: list('number', undefined, 2),
              col_b: list('string', undefined, 2),
            })
          )
        ),
        value: [{col_a: [0, 0], col_b: ['hello_0', 'hello_1']}],
      }
    );
  });

  it('test opJoinAll - complex', async () => {
    await testNode(
      opJoinAll({
        arrs: opArray({
          0: opArray({
            0: opDict({
              col_a: constNumber(0),
              col_b: opDict({
                col_c: constString('hello_0'),
              } as any),
            } as any),
            1: opDict({
              col_a: constNumber(1),
              col_b: constNone(),
            } as any),
          } as any),
          1: opArray({
            0: opDict({
              col_a: constNumber(0),
              col_b: constNone(),
            } as any) as any,
            1: opDict({
              col_a: constNumber(2),
              col_b: constNone(),
            } as any),
          } as any),
        } as any),
        joinFn: constFunction(
          {
            row: typedDict({
              col_a: 'number',
              col_b: 'string',
            }),
          },
          ({row}) => {
            return opPick({
              obj: row,
              key: constString('col_a'),
            });
          }
        ),
      } as any),
      {
        type: list(
          taggedValue(
            typedDict({joinKey: 'string', joinObj: 'number'}),
            typedDict({
              col_a: list('number'),
              col_b: list(maybe(typedDict({col_c: 'string'}))),
            })
          )
        ),
        resolvedType: list(
          taggedValue(
            typedDict({joinKey: 'string', joinObj: 'number'}),
            typedDict({
              col_a: list('number', undefined, 2),
              col_b: list(maybe(typedDict({col_c: 'string'})), undefined, 2),
            })
          )
        ),
        value: [
          {
            col_a: [0, 0],
            col_b: [
              {
                col_c: 'hello_0',
              },
              null,
            ],
          },
        ],
      }
    );
  });

  it('test opJoinAll return type', async () => {
    const arrType = maybe(
      taggedValue(
        typedDict({outerTag: 'string'}),
        list(
          maybe(
            taggedValue(
              typedDict({innerTag: 'string'}),
              list(
                maybe(
                  taggedValue(
                    typedDict({rowTag: 'string'}),
                    typedDict({col_a: 'number', col_b: 'string'})
                  )
                )
              )
            )
          )
        )
      )
    );
    const joinFnRetType = taggedValue(
      typedDict({joinFnKeyTag: 'number'}),
      typedDict({joinFnKeyObj: 'string'})
    );
    const joinFnType = functionType({row: typedDict({})}, joinFnRetType);
    const returnType = opJoinAllReturnType(arrType as any, joinFnType as any);
    const expType = maybe(
      taggedValue(
        typedDict({outerTag: 'string'}),
        list(
          taggedValue(
            typedDict({joinKey: 'string', joinObj: joinFnRetType}),
            typedDict({
              col_a: list(
                taggedValue(
                  taggedValue(
                    typedDict({innerTag: 'string'}),
                    typedDict({rowTag: 'string'})
                  ),
                  'number'
                )
              ),
              col_b: list(
                taggedValue(
                  taggedValue(
                    typedDict({innerTag: 'string'}),
                    typedDict({rowTag: 'string'})
                  ),
                  'string'
                )
              ),
            })
          )
        )
      )
    );
    console.log(typeToString(returnType, false));
    console.log(typeToString(expType, false));
    expect(normalizeType(returnType)).toEqual(normalizeType(expType));
  });
});

describe('randomSample utility', () => {
  const inputArray = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

  it('returns an array with the correct length', () => {
    const sampleSize = 5;
    const sampledArray = randomlyDownsample(inputArray, sampleSize);
    expect(sampledArray.length).toBe(sampleSize);
  });

  it('does not contain duplicate elements', () => {
    const sampleSize = 5;
    const sampledArray = randomlyDownsample(inputArray, sampleSize);
    const set = new Set(sampledArray);
    expect(set.size).toBe(sampleSize);
  });

  it('only contains elements present in the input array', () => {
    const sampleSize = 5;
    const sampledArray = randomlyDownsample(inputArray, sampleSize);
    for (const element of sampledArray) {
      expect(inputArray).toContain(element);
    }
  });

  it('returns the original array if n >= array.length', () => {
    const sampleSize = inputArray.length;
    const sampledArray = randomlyDownsample(inputArray, sampleSize);
    expect(sampledArray).toEqual(inputArray);
  });

  it('throws an error for invalid input', () => {
    const sampleSize = -1;
    expect(() => randomlyDownsample(inputArray, sampleSize)).toThrowError(
      'Invalid input: n must be a non-negative integer.'
    );
  });

  it('handles length 0 list and 0 sample size', () => {
    const sampleSize = 0;
    expect(randomlyDownsample(inputArray, sampleSize)).toEqual([]);

    const inputArray2: any[] = [];
    expect(randomlyDownsample(inputArray2, sampleSize)).toEqual([]);
  });

  it('check that the output is sorted', () => {
    const sampleSize = 5;
    const sampledArray = randomlyDownsample(inputArray, sampleSize);
    expect(sampledArray).toEqual(sampledArray.sort());
  });
});

describe('sample op', () => {
  const inputArray = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  const arrayNode = constNumberList(inputArray);
  const sampleSize = 5;
  const sampleSizeNode = constNumber(sampleSize);
  const sampleNode = opRandomlyDownsample({
    arr: arrayNode,
    n: sampleSizeNode,
  });

  it('returns an array with the correct length', async () => {
    const client = await testClient();
    const sampledArray = await client.query(sampleNode);
    expect(sampledArray.length).toBe(sampleSize);
  });

  it('does not contain duplicate elements', async () => {
    const client = await testClient();
    const sampledArray = await client.query(sampleNode);
    const set = new Set(sampledArray);
    expect(set.size).toBe(sampleSize);
  });

  it('only contains elements present in the input array', async () => {
    const client = await testClient();
    const sampledArray = await client.query(sampleNode);
    for (const element of sampledArray) {
      expect(inputArray).toContain(element);
    }
  });

  it('returns the original array if n >= array.length', async () => {
    const client = await testClient();
    const sampleNode = opRandomlyDownsample({
      arr: arrayNode,
      n: constNumber(inputArray.length),
    });
    const sampledArray = await client.query(sampleNode);
    expect(sampledArray).toEqual(inputArray);
  });

  it('throws an error for invalid input', async () => {
    const sampleSize = constNumber(-1);
    const sampleNode = opRandomlyDownsample({
      arr: arrayNode,
      n: sampleSize,
    });
    const client = await testClient();
    expect(client.query(sampleNode)).rejects.toThrowError(
      'Invalid input: n must be a non-negative integer.'
    );
  });

  it('check that the output is sorted', async () => {
    const client = await testClient();
    const sampledArray = await client.query(sampleNode);
    expect(sampledArray).toEqual(sampledArray.sort());
  });

  it('check that op handles length 0 list or 0 sample size', async () => {
    const client = await testClient();
    const sampleSize = constNumber(0);
    const sampleNode = opRandomlyDownsample({
      arr: arrayNode,
      n: sampleSize,
    });
    expect(await client.query(sampleNode)).toEqual([]);

    const inputArray = constNumberList([]);
    const sampleNode2 = opRandomlyDownsample({
      arr: inputArray,
      n: sampleSizeNode,
    });
    expect(await client.query(sampleNode2)).toEqual([]);
  });
});

describe('opRandomGaussian', () => {
  it('should generate samples with the correct mean and standard deviation', async () => {
    const mean = 5;
    const std = 2;
    const n = 100000;
    const node = opRandomGaussian({
      mean: constNumber(mean),
      std: constNumber(std),
      n: constNumber(n),
    });
    const client = await testClient();
    const samples = await client.query(node);
    const sampleMean = samples.reduce((acc: any, val: any) => acc + val, 0) / n;
    const sampleStd = Math.sqrt(
      samples.reduce((acc: any, val: any) => acc + (val - sampleMean) ** 2, 0) /
        n
    );
    expect(sampleMean).toBeCloseTo(mean, 1);
    expect(sampleStd).toBeCloseTo(std, 1);
  });

  it('should generate samples with the correct length', async () => {
    const n = 1000;
    const node = opRandomGaussian({
      mean: constNumber(0),
      std: constNumber(1),
      n: constNumber(n),
    });
    const client = await testClient();
    const samples = await client.query(node);
    expect(samples.length).toBe(n);
  });
});
