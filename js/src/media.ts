
// Define WeaveImage type
interface WeaveImage {
    _type: 'WeaveImage';
    data: Buffer;
    imageType: 'png';
}

export function weaveImage({ data, imageType }: { data: Buffer, imageType: 'png' }): WeaveImage {
    return {
        _type: 'WeaveImage',
        data,
        imageType
    };
}

// Function to check if a value is a WeaveImage
export function isWeaveImage(value: any): value is WeaveImage {
    return value && value._type === 'WeaveImage' && Buffer.isBuffer(value.data) && value.imageType === 'png';
}