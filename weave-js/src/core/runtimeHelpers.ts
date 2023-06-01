import type {
  OpDef,
  OpDefGeneratedWeave,
  OpDefLowLevel,
  OpDefWeave,
} from './opStore/types';

export const opDefIsLowLevel = (opDef: OpDef): opDef is OpDefLowLevel => {
  return (opDef as any).resolver != null;
};

export const opDefIsWeave = (opDef: OpDef): opDef is OpDefWeave => {
  return (opDef as any).body != null;
};

export const opDefIsGeneratedWeave = (
  opDef: OpDef
): opDef is OpDefGeneratedWeave => {
  return (opDef as any).expansion != null;
};
