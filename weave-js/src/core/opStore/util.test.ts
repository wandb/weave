import {OutputNode} from '../model';
import {varNode} from '../model/graph/construction';
import {EditingOutputNode} from '../model/graph/editing/types';
import {
  opIndex,
  opNumberAdd,
  opNumberDiv,
  opNumberEqual,
  opNumberMult,
  opNumberPowBinary,
  opNumbersAvg,
  opNumberSub,
} from '../ops/primitives';
import {StaticOpStore} from './static';
import {opNeedsParens} from './util';

it('opNeedsParens', () => {
  // in x + y + z,
  // x + y DOES NOT require parentheses
  const allAddition = opNumberAdd({
    lhs: opNumberAdd({
      lhs: varNode('number', 'x'),
      rhs: varNode('number', 'y'),
    }),
    rhs: varNode('number', 'z'),
  });
  expect(
    opNeedsParens(
      (allAddition.fromOp.inputs.lhs as EditingOutputNode).fromOp,
      allAddition,
      StaticOpStore.getInstance()
    )
  ).toBe(false);

  // in x + (y + z),
  // y + z DOES require parentheses
  const allAdditionWithRightParens = opNumberAdd({
    lhs: varNode('number', 'x'),
    rhs: opNumberAdd({
      lhs: varNode('number', 'y'),
      rhs: varNode('number', 'z'),
    }),
  });
  expect(
    opNeedsParens(
      (allAdditionWithRightParens.fromOp.inputs.rhs as EditingOutputNode)
        .fromOp,
      allAdditionWithRightParens,
      StaticOpStore.getInstance()
    )
  ).toBe(true);

  // in x * (y / z)
  // y / z DOES require parentheses
  // (otherwise we get the wrong expression due to left associativity)
  const rightAssociativeDivide = opNumberMult({
    lhs: varNode('number', 'x'),
    rhs: opNumberDiv({
      lhs: varNode('number', 'y'),
      rhs: varNode('number', 'z'),
    }),
  });
  expect(
    opNeedsParens(
      (rightAssociativeDivide.fromOp.inputs.rhs as EditingOutputNode).fromOp,
      rightAssociativeDivide,
      StaticOpStore.getInstance()
    )
  ).toBe(true);

  // in (x + y) * z,
  // x + y DOES require parentheses
  const additionUnderMultiplication = opNumberMult({
    lhs: opNumberAdd({
      lhs: varNode('number', 'x'),
      rhs: varNode('number', 'y'),
    }),
    rhs: varNode('number', 'z'),
  });
  expect(
    opNeedsParens(
      (additionUnderMultiplication.fromOp.inputs.lhs as EditingOutputNode)
        .fromOp,
      additionUnderMultiplication,
      StaticOpStore.getInstance()
    )
  ).toBe(true);

  // in x + y = z,
  // x + y DOES NOT require parentheses
  const additionEqual = opNumberEqual({
    lhs: opNumberAdd({
      lhs: varNode('number', 'x'),
      rhs: varNode('number', 'y'),
    }),
    rhs: varNode('number', 'z'),
  });
  expect(
    opNeedsParens(
      (additionEqual.fromOp.inputs.lhs as EditingOutputNode).fromOp,
      additionEqual,
      StaticOpStore.getInstance()
    )
  ).toBe(false);

  // in x + y - z,
  // x + y DOES NOT require parentheses
  const additionUnderSubtraction = opNumberAdd({
    lhs: opNumberSub({
      lhs: varNode('number', 'x'),
      rhs: varNode('number', 'y'),
    }),
    rhs: varNode('number', 'z'),
  });
  expect(
    opNeedsParens(
      (additionUnderSubtraction.fromOp.inputs.lhs as EditingOutputNode).fromOp,
      additionUnderSubtraction,
      StaticOpStore.getInstance()
    )
  ).toBe(false);

  // in x ** y ** z,
  // y ** z DOES NOT require parentheses
  const exponentiation = opNumberPowBinary({
    lhs: varNode('number', 'x'),
    rhs: opNumberPowBinary({
      lhs: varNode('number', 'y'),
      rhs: varNode('number', 'z'),
    }),
  });
  expect(
    opNeedsParens(
      (exponentiation.fromOp.inputs.rhs as EditingOutputNode).fromOp,
      exponentiation,
      StaticOpStore.getInstance()
    )
  ).toBe(false);

  // in (x ** y) ** z,
  // x ** y DOES require parentheses due to right associativity
  const exponentiationLeft = opNumberPowBinary({
    lhs: opNumberPowBinary({
      lhs: varNode('number', 'x'),
      rhs: varNode('number', 'y'),
    }),
    rhs: varNode('number', 'z'),
  });
  expect(
    opNeedsParens(
      (exponentiationLeft.fromOp.inputs.lhs as EditingOutputNode).fromOp,
      exponentiationLeft,
      StaticOpStore.getInstance()
    )
  ).toBe(true);

  // in (x - y).avg(),
  // x - y DOES require parentheses
  const subtractionUnderAvg = opNumbersAvg({
    numbers: opNumberSub({
      lhs: varNode('number', 'x'),
      rhs: varNode('number', 'y'),
    }),
  });
  expect(
    opNeedsParens(
      (subtractionUnderAvg.fromOp.inputs.numbers as EditingOutputNode).fromOp,
      subtractionUnderAvg,
      StaticOpStore.getInstance()
    )
  ).toBe(true);

  // in arr.index(x + y),
  // x + y DOES NOT require parentheses
  const additionUnderIndex = opIndex({
    arr: varNode(
      {
        type: 'list',
        objectType: 'any',
      },
      'arr'
    ),
    index: opNumberAdd({
      lhs: varNode('number', 'x'),
      rhs: varNode('number', 'y'),
    }) as OutputNode<'number'>,
  });
  expect(
    opNeedsParens(
      (additionUnderIndex.fromOp.inputs.index as EditingOutputNode).fromOp,
      additionUnderIndex,
      StaticOpStore.getInstance()
    )
  ).toBe(false);
});
