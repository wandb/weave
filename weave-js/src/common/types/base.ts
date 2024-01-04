/*** Generic types go in here ***/

// use this sparingly!
export interface GenericObject {
  [key: string]: any;
}

///// Simple type helpers
// Type T minus the single key K
export type Omit<T, K> = Pick<T, Exclude<keyof T, K>>;
// Type T minus all keys in K
export type Subtract<T, K> = Omit<T, keyof K>;
// Type T minus null and undefined
export type ExcludeNullish<T> = Exclude<T, null | undefined>;

// Get type contained in array
// tslint:disable-next-line
export type Unpack<A> = A extends Array<infer E> ? E : A;

export type Class<T> = new (...args: any[]) => T;

// RequireSome
//
// Requires a subset of keys from the original object
//
// Examples:
//
// interface Foo {a: string, b: string, c: string}
// Valid:
//   RequireSome<Foo,"a">       = {a: "baz", c: "bingo"}
//   RequireSome<Foo,"a" | "b"> = {a: "baz", b: "bar", c: "bingo"}
//   RequireSome<Foo,"a" | "b"> = {a: "baz", b: "bar"}
// Invalid:
//   RequireSome<Foo,"b">       = {a: "baz"}
//   RequireSome<Foo,"b" | "c"> = {c: "baz"}
//   RequireSome<Foo,"c">       = {c: "baz"}
export type RequireSome<T, U extends keyof T> = T & Required<Pick<T, U>>;

// Subset
// Requires only a subset of keys from the given type:
// e.g.
//
// Examples
//
// interface Foo {a: string, b: string, c: string}
// Valid:
//   Subset<Foo,"a">       = {a: "baz", b: "bar", c: "bingo"}
//   Subset<Foo,"a">       = {a: "baz", b: "bar"}
//   Subset<Foo,"a" | "b"> = {a: "baz", b: "bar"}
//   Subset<Foo,"a">       = {a: "baz"}
// Invalid:
//   Subset<Foo,"b">       = {a: "baz"}
//   Subset<Foo,"b" | "c"> = {c: "baz"}
export type Subset<T, U extends keyof T> = Partial<T> & Required<Pick<T, U>>;

export type DeepPartial<T> = {[P in keyof T]?: DeepPartial<T[P]>};

export type PartialSome<T, U extends keyof T> = Omit<T, U> &
  Partial<Pick<T, U>>;

// Parameters
// returns the parameter types of a function type
export type Parameters<F> = F extends (...args: infer P) => any ? P : never;

// NOTE(Adrian): I added this type helper to help us type subobjects inside generated GQL types...
//  It won't work until we upgrade to TS 4+ though :(
//  "I guess you guys aren't ready for that yet...but your kids are gonna love it!"
// Extracts the type of a nested property in T, removing any nulls in the process.
// e.g., PropType<{a: {b: {c: string}}}, "a.b"> == {c: string}.
// export type PropType<T, P extends string> = P extends keyof T
//   ? NonNullable<T[P]>
//   : P extends `${infer L}.${infer R}`
//   ? L extends keyof T
//     ? PropType<NonNullable<T[L]>, R>
//     : never
//   : never;

// URL params from Route component
export interface Match {
  isExact: boolean;
  params: MatchParams;
  path: string;
  url: string;
}

export interface MatchParams {
  entityName?: string;
  projectName?: string;
  runName?: string;
  displayName?: string;
  groupName?: string;
  reportNameAndID?: string;
  sweepName?: string;
  jobId?: string;
  jobTab?: string;
  queueId?: string;
  tab?: string;
  filePath?: string;
  artifactTypeName?: string;
  artifactCollectionName?: string;
  artifactCommitHash?: string;
  artifactCollectionView?: string;
  artifactTab?: string;
  registryName?: string;
}
