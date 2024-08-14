export type CustomWeaveTypePayload<
  T extends string = string,
  FP extends {[filename: string]: string} = {[filename: string]: string}
> = {
  _type: 'CustomWeaveType';
  weave_type: {
    type: T;
  };
  files: FP;
  load_op?: string;
};

export const isCustomWeaveTypePayload = (
  data: any
): data is CustomWeaveTypePayload => {
  if (typeof data !== 'object' || data === null) {
    return false;
  }
  if (data._type !== 'CustomWeaveType') {
    return false;
  }
  if (
    typeof data.weave_type !== 'object' ||
    data.weave_type === null ||
    typeof data.weave_type.type !== 'string'
  ) {
    return false;
  }
  if (typeof data.files !== 'object' || data.files === null) {
    return false;
  }
  if (data.load_op !== undefined && typeof data.load_op !== 'string') {
    return false;
  }
  return true;
};
