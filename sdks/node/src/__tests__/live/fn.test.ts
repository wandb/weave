import {init, login} from '../../clientApi';
import {CallableObject} from '../../fn';
import {op} from '../../op';
import {WeaveObjectParameters} from '../../weaveObject';

interface ParametrizedFunctionOptions extends WeaveObjectParameters {
  magicNumber?: number;
}

class ParametrizedFunction extends CallableObject<
  {input: number},
  {output: number}
> {
  private magicNumber: number;

  constructor(options: ParametrizedFunctionOptions = {}) {
    super(options);
    this.magicNumber = options.magicNumber ?? 42;

    this.run = op(this, this.run, {
      parameterNames: ['input'],
    });
  }

  async run(input: {input: number}): Promise<{output: number}> {
    return {output: input.input + this.magicNumber};
  }
}

describe.skip('Fn', () => {
  beforeEach(async () => {
    await login(process.env.WANDB_API_KEY ?? '');
  });

  test('use fn', async () => {
    const client = await init('test-project');

    const fn = new ParametrizedFunction({magicNumber: 7});
    const res = await fn.run({input: 1});
    expect(res).toEqual({output: 8});
  });
});
