/** Represents an object that can be encrypted as valid JSON */
export interface JSONObject {
  [member: string]: Value | null;
}

export type Primitive = string | number | boolean;

export interface Arr extends Array<Value> {}

export type Value = Primitive | JSONObject | Arr;
