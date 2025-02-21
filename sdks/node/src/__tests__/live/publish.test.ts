import {init, login} from '../../clientApi';
import {Dataset, op, weaveAudio, weaveImage} from '../../index';

describe.skip('Publishing Various Data Types', () => {
  beforeEach(async () => {
    await login(process.env.WANDB_API_KEY ?? '');
  });

  const primitiveOp = op(async function primitive(input: string) {
    return `Hi ${input}!`;
  });

  const jsonOp = op(async function json(name: string, age: number) {
    return {name, age};
  });

  const imageOp = op(async function image() {
    const width = 16;
    const height = 16;
    const buffer = Buffer.alloc(width * height * 4); // 4 bytes per pixel (RGBA)

    for (let i = 0; i < buffer.length; i++) {
      buffer[i] = Math.floor(Math.random() * 256);
    }

    return weaveImage({
      data: buffer,
      imageType: 'png',
    });
  });

  const audioOp = op(async function audio() {
    // Create a small audio buffer with random samples
    const sampleRate = 44100; // Standard CD quality
    const duration = 0.1; // 100ms
    const numSamples = Math.floor(sampleRate * duration);
    const buffer = Buffer.alloc(numSamples * 2); // 2 bytes per sample for 16-bit audio

    for (let i = 0; i < buffer.length; i += 2) {
      // Generate random 16-bit sample between -32768 and 32767
      const sample = Math.floor(Math.random() * 65536 - 32768);
      buffer.writeInt16LE(sample, i);
    }

    return weaveAudio({
      data: buffer,
      audioType: 'wav',
    });
  });

  const datasetOp = op(async function dataset() {
    return new Dataset({
      id: 'my-dataset',
      rows: [
        {name: 'Alice', age: 10},
        {name: 'Bob', age: 20},
        {name: 'Charlie', age: 30},
      ],
    });
  });

  test('publish various data types', async () => {
    const client = await init('test-project');

    const primitiveResult = await primitiveOp('world');
    expect(primitiveResult).toBe('Hi world!');

    const jsonResult = await jsonOp('Alice', 10);
    expect(jsonResult).toEqual({name: 'Alice', age: 10});

    const imageResult = await imageOp();
    expect(imageResult).toHaveProperty('data');
    expect(imageResult).toHaveProperty('imageType', 'png');

    const audioResult = await audioOp();
    expect(audioResult).toHaveProperty('data');
    expect(audioResult).toHaveProperty('audioType', 'wav');

    const datasetResult = await datasetOp();
    expect(datasetResult).toBeInstanceOf(Dataset);
    expect(datasetResult.rows).toHaveLength(3);
  }, 20000); // Adding explicit timeout here, though I'm not sure why it's needed
});
