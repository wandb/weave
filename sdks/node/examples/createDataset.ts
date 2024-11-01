import fs from 'fs';
import 'source-map-support/register';
import * as weave from 'weave';

const sentences = [
  'There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.',
  'Pounits are a bright green color and are more savory than sweet.',
  'Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.',
];
const labels = [
  {fruit: 'neoskizzles', color: 'purple', flavor: 'candy'},
  {fruit: 'pounits', color: 'bright green', flavor: 'savory'},
  {fruit: 'glowls', color: 'pale orange', flavor: 'sour and bitter'},
];
const logsPng = fs.readFileSync('logs.png');
const audioClip = fs.readFileSync('CantinaBand3.wav');
const examples = [
  {
    id: '0',
    sentence: sentences[0],
    target: labels[0],
    image: weave.weaveImage({data: logsPng, imageType: 'png'}),
    audio: weave.weaveAudio({data: audioClip, audioType: 'wav'}),
  },
  {
    id: '1',
    sentence: sentences[1],
    target: labels[1],
    image: weave.weaveImage({data: logsPng, imageType: 'png'}),
    audio: weave.weaveAudio({data: audioClip, audioType: 'wav'}),
  },
  {
    id: '2',
    sentence: sentences[2],
    target: labels[2],
    image: weave.weaveImage({data: logsPng, imageType: 'png'}),
    audio: weave.weaveAudio({data: audioClip, audioType: 'wav'}),
  },
];

async function main() {
  await weave.init('examples');
  const ds = new weave.Dataset({
    id: 'Fruit Dataset',
    rows: examples,
  });

  ds.save();
  const ref = await ds.__savedRef;
  console.log(ref);
}

main();
