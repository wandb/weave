import 'source-map-support/register';
import fs from 'fs';
import { init, Dataset, weaveImage } from 'weave';

const sentences = [
    "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.",
    "Pounits are a bright green color and are more savory than sweet.",
    "Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.",
    "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.",
]
const labels = [
    { "fruit": "neoskizzles", "color": "purple", "flavor": "candy" },
    { "fruit": "pounits", "color": "bright green", "flavor": "savory" },
    { "fruit": "glowls", "color": "pale orange", "flavor": "sour and bitter" },
]
const logsPng = fs.readFileSync('logs.png')
const examples = [
    { "id": "0", "sentence": sentences[0], "target": labels[0], "image": weaveImage({ data: logsPng, imageType: 'png' }) },
    { "id": "1", "sentence": sentences[1], "target": labels[1], "image": weaveImage({ data: logsPng, imageType: 'png' }) },
    { "id": "2", "sentence": sentences[2], "target": labels[2], "image": weaveImage({ data: logsPng, imageType: 'png' }) },
]

async function main() {
    await init('weavejsdev-dataset2');
    const ds = new Dataset({
        id: "Fruit Dataset",
        rows: examples
    });
    const ref = await ds.save()
    console.log(ref)
}

main();

