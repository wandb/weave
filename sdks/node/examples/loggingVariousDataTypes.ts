import fs from 'fs';
import * as weave from 'weave';

const primitiveOp = weave.op(async function primitive(input: string) {
  return `Hi ${input}!`;
});

const jsonOp = weave.op(async function json(name: string, age: number) {
  return {name, age};
});

const imageOp = weave.op(async function image() {
  return weave.weaveImage({
    data: fs.readFileSync('logs.png'),
    imageType: 'png',
  });
});

const audioOp = weave.op(async function audio() {
  return weave.weaveAudio({
    data: fs.readFileSync('CantinaBand3.wav'),
    audioType: 'wav',
  });
});

const datasetOp = weave.op(async function dataset() {
  return new weave.Dataset({
    id: 'my-dataset',
    rows: [
      {name: 'Alice', age: 10},
      {name: 'Bob', age: 20},
      {name: 'Charlie', age: 30},
    ],
  });
});

async function main() {
  await weave.init('examples');

  const primitivePromise = primitiveOp('world');
  const jsonPromise = jsonOp('Alice', 10);
  const imagePromise = imageOp();
  const audioPromise = audioOp();
  const datasetPromise = datasetOp();

  console.log('Primitive Result:', await primitivePromise);
  console.log('JSON Result:', await jsonPromise);
  console.log('Image Result:', await imagePromise);
  console.log('Audio Result:', await audioPromise);
  console.log('Dataset Result:', await datasetPromise);
}

main();
