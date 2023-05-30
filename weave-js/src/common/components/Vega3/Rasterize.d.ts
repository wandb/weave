/**
 * Converts pixel data into a canvas bitmap.
 */
declare function Rasterize(params: any): void;

// eslint-disable-next-line no-redeclare
declare namespace Rasterize {
  export const Definition: {
    type: string;
    metadata: {
      generates: boolean;
    };
    params: (
      | {
          name: string;
          type: string;
          required: boolean;
        }
      | {
          name: string;
          type: string;
          required?: undefined;
        }
    )[];
  };
}
export default Rasterize;
