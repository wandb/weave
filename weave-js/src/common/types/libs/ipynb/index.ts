// If we ever have new major versions, we need to update this file with the
// new import and union the exported types

import * as V4 from './types_gen/nbformat.v4.schema';

export type NbformatSchema = V4.NbformatV4Schema;
export type Cell = V4.Cell;
export type DisplayData = V4.DisplayData;
export type ExecuteResult = V4.ExecuteResult;
