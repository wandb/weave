import typing
import math

from ..api import type, op, use
from ..weave_types import Function, Float
from ..ops_primitives import dict_ops, Number

from ..weave_internal import define_fn, call_fn


@type()
class NumberBin:
    start: float
    stop: float


@op(
    input_type={"step": Float()},
    output_type=Function(
        input_types={"row": Float()},
        output_type=NumberBin.WeaveType(),  # type: ignore
    ),
)
def number_bins_fixed(step):
    def body(row):
        if step <= 0:
            raise ValueError("Step must be greater than zero.")
        mult = 1.0 / step
        start_node = Number.floor(row * mult) / mult
        return dict_ops.dict_(start=start_node, stop=start_node + step)

    return define_fn({"row": Float()}, body)


@op(
    output_type=Function(
        input_types={"row": Float()}, output_type=NumberBin.WeaveType()  # type: ignore
    )
)
def numbers_bins_equal(arr: typing.List[float], bins: float):
    arr_min = min(arr) if len(arr) > 0 else 0
    arr_max = max(arr) if len(arr) > 0 else 0
    step = (arr_max - arr_min) / bins
    return use(number_bins_fixed(step))


@op(
    input_type={
        "in_": Float(),
        "bin_fn": Function(
            input_types={"row": Float()}, output_type=NumberBin.WeaveType()  # type: ignore
        ),
    }
)
def number_bin(in_, bin_fn) -> NumberBin:
    call = call_fn(bin_fn, {"row": in_})
    return use(call)


"""
export const opNumberBinsFixed = OpKinds.makeStandardOp({
  hidden: true,
  name: 'root-number-binsfixed',
  renderInfo: {type: 'function'},
  argTypes: {step: 'number'},
  description: '', // TODO: Add description if unhidden
  argDescriptions: {
    step: '', // TODO: Add description if unhidden
  },
  returnValueDescription: '', // TODO: Add description if unhidden
  returnType: inputTypes => ({
    type: 'function',
    inputTypes: {row: TypeHelpers.maybe('number')},
    outputType: TypeHelpers.numberBin,
  }),
  resolver: inputs => {
    const mult = 1 / inputs.step;
    return opDict({
      start: opNumberDiv({
        lhs: opNumberFloor({
          in: opNumberMult({
            lhs: Graph.varNode('number', 'row'),
            rhs: constNumber(mult),
          }) as any,
        }),
        rhs: constNumber(mult),
      }),
      stop: opNumberAdd({
        lhs: opNumberDiv({
          lhs: opNumberFloor({
            in: opNumberMult({
              lhs: Graph.varNode('number', 'row'),
              rhs: constNumber(mult),
            }) as any,
          }),
          rhs: constNumber(mult),
        }),
        rhs: constNumber(inputs.step),
      }),
    } as any);
  },
});

export const opNumbersBinEqual = OpKinds.makeBasicOp({
  hidden: true,
  name: 'numbers-binsequal',
  argTypes: {arr: {type: 'list', objectType: 'number'}, bins: 'number'},
  description: '', // TODO: Add description if unhidden
  argDescriptions: {
    arr: '', // TODO: Add description if unhidden
    bins: '', // TODO: Add description if unhidden
  },
  returnValueDescription: '', // TODO: Add description if unhidden
  returnType: inputTypes => ({
    type: 'function',
    inputTypes: {row: 'number'},
    outputType: TypeHelpers.numberBin,
  }),
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    // What do we do? Do we min max here? But we should
    // be doing that with ops.... :(
    const bins = inputs.bins;
    const arrMin = _.min(inputs.arr as number[]) ?? 0;
    const arrMax = _.max(inputs.arr as number[]) ?? 0;
    const step = (arrMax - arrMin) / bins;

    const binOp = opNumberBinsFixed({step: constNumber(step)});
    const result = (await engine().executeNodes([binOp], true))[0];
    return result;
  },
});

export const opNumberBin = OpKinds.makeStandardOp({
  hidden: true,
  name: 'number-bin',
  argTypes: {
    in: TypeHelpers.maybe('number'),
    binFn: {
      type: 'function',
      inputTypes: {row: 'number'},
      outputType: TypeHelpers.numberBin,
    },
  },
  description: '', // TODO: Add description if unhidden
  argDescriptions: {
    in: '', // TODO: Add description if unhidden
    binFn: '', // TODO: Add description if unhidden
  },
  returnValueDescription: '', // TODO: Add description if unhidden
  returnType: inputTypes => TypeHelpers.numberBin,
  resolver: async (
    inputs,
    inputTypes,
    rawInputs,
    forwardGraph,
    forwardOp,
    context,
    engine
  ) => {
    const input = getValueFromTaggedValue(inputs.in);
    const binFn = inputs.binFn;
    // console.time('opGroupBy-construct-calls');
    const frame = {
      ...context.frame,
      row: constNumber(input),
    };
    const call = callFunction.default(binFn, frame);

    const result = (await engine().executeNodes([call], true))[0];
    return result;
  },
});
"""

"""
@op(
    output_type=Function(
        input_types={"val": Float()}, output_type=NumberBin.WeaveType()  # type: ignore
    )
)
def number_bins_equal(min: float, max: float, n_bins: int):
    bins = np.linspace(min, max, n_bins + 1)
    number_bins = [NumberBin(i, bins[i], bins[i + 1]) for i in range(len(bins) - 1)]

    def assign_bin(val: float) -> typing.Optional[NumberBin]:
        if val > bins[-1] or val < bins[0]:
            return None
        index = bisect.bisect_left(bins, val) - 1
        return number_bins[index]

    return assign_bin
"""
