import {init, login} from '../../clientApi';
import {op} from '../../op';
import {WeaveObject} from '../../weaveObject';

class ExampleObject extends WeaveObject {
  constructor(
    public name: string,
    public value: number
  ) {
    super({});

    this.method = op(this.method);
  }

  async method() {
    return this.name + '!';
  }
}

describe('weaveObject', () => {
  beforeEach(async () => {
    await login(process.env.WANDB_API_KEY ?? '');
  });

  test('basic-example', async () => {
    // TODO: Do we support saving  basic objects?
    // const client = await init('test-project');
    // const obj = { name: 'test', value: 1 };
    // client.saveObject(obj as any);
    // const ref = await (obj as any).__savedRef;
    // console.log(ref);
  });

  test('class-example', async () => {
    const client = await init('test-project');
    const obj = new ExampleObject('test', 1);

    // save an object
    client.publish(obj);

    const ref = await obj.__savedRef;
    const [entity, project] = ref?.projectId.split('/') ?? [];
    expect(project).toBe('test-project');
    console.log(ref);

    // also save its ops
  });
});
