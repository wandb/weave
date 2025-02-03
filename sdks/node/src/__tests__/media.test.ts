import {weaveAudio, weaveImage} from '../media';

describe('media', () => {
  test('logging weaveImage', () => {
    const imageBuffer = Buffer.from('mock image data');
    const image = weaveImage({data: imageBuffer});

    expect(image).toHaveProperty('_weaveType', 'Image');
    expect(image).toHaveProperty('data', imageBuffer);
    expect(image).toHaveProperty('imageType', 'png');
  });

  test('logging weaveAudio', () => {
    const audioBuffer = Buffer.from('mock audio data');
    const audio = weaveAudio({data: audioBuffer});

    expect(audio).toHaveProperty('_weaveType', 'Audio');
    expect(audio).toHaveProperty('data', audioBuffer);
    expect(audio).toHaveProperty('audioType', 'wav');
  });
});
