// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

/**
 * Logical AND. All conditions must evaluate to true.
 *
 * Example:
 * ` { "$and": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "predict"}]}, {"$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 1000}]} ] } `
 */
export interface AndOperation {
  $and: Array<Operation>;
}

/**
 * Case-insensitive substring match.
 *
 * Not part of MongoDB. Weave-specific addition.
 *
 * Example:
 * ` { "$contains": { "input": {"$getField": "display_name"}, "substr": {"$literal": "llm"}, "case_insensitive": true } } `
 */
export interface ContainsOperation {
  /**
   * Specification for the `$contains` operation.
   *
   * - `input`: The string to search.
   * - `substr`: The substring to search for.
   * - `case_insensitive`: If true, match is case-insensitive.
   */
  $contains: ContainsSpec;
}

/**
 * Specification for the `$contains` operation.
 *
 * - `input`: The string to search.
 * - `substr`: The substring to search for.
 * - `case_insensitive`: If true, match is case-insensitive.
 */
export interface ContainsSpec {
  input: Operation;

  substr: Operation;

  case_insensitive?: boolean | null;
}

/**
 * Convert the input value to a specific type (e.g., `int`, `bool`, `string`).
 *
 * Example:
 * ` { "$convert": { "input": {"$getField": "inputs.value"}, "to": "int" } } `
 */
export interface ConvertOperation {
  /**
   * Specifies conversion details for `$convert`.
   *
   * - `input`: The operand to convert.
   * - `to`: The type to convert to.
   */
  $convert: ConvertSpec;
}

/**
 * Specifies conversion details for `$convert`.
 *
 * - `input`: The operand to convert.
 * - `to`: The type to convert to.
 */
export interface ConvertSpec {
  input: Operation;

  to: 'double' | 'string' | 'int' | 'bool' | 'exists';
}

/**
 * Equality check between two operands.
 *
 * Example: ` { "$eq": [{"$getField": "op_name"}, {"$literal": "predict"}] } `
 */
export interface EqOperation {
  $eq: Array<unknown>;
}

/**
 * Access a field on the traced call.
 *
 * Supports dot notation for nested access, e.g. `summary.usage.tokens`.
 *
 * Only works on fields present in the `CallSchema`, including:
 *
 * - Top-level fields like `op_name`, `trace_id`, `started_at`
 * - Nested fields like `inputs.input_name`, `summary.usage.tokens`, etc.
 *
 * Example: ` {"$getField": "op_name"} `
 */
export interface GetFieldOperator {
  $getField: string;
}

/**
 * Greater than comparison.
 *
 * Example:
 * ` { "$gt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
 */
export interface GtOperation {
  $gt: Array<unknown>;
}

/**
 * Greater than or equal comparison.
 *
 * Example:
 * ` { "$gte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
 */
export interface GteOperation {
  $gte: Array<unknown>;
}

/**
 * Membership check.
 *
 * Returns true if the left operand is in the list provided as the second operand.
 *
 * Example:
 * ` { "$in": [ {"$getField": "op_name"}, [{"$literal": "predict"}, {"$literal": "generate"}] ] } `
 */
export interface InOperation {
  $in: Array<unknown>;
}

/**
 * Represents a constant value in the query language.
 *
 * This can be any standard JSON-serializable value.
 *
 * Example: ` {"$literal": "predict"} `
 */
export interface LiteralOperation {
  $literal: string | number | boolean | { [key: string]: LiteralOperation } | Array<LiteralOperation> | null;
}

/**
 * Logical NOT. Inverts the condition.
 *
 * Example:
 * ` { "$not": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "debug"}]} ] } `
 */
export interface NotOperation {
  $not: Array<unknown>;
}

/**
 * Represents a constant value in the query language.
 *
 * This can be any standard JSON-serializable value.
 *
 * Example: ` {"$literal": "predict"} `
 */
export type Operation =
  | LiteralOperation
  | GetFieldOperator
  | ConvertOperation
  | unknown
  | AndOperation
  | OrOperation
  | NotOperation
  | EqOperation
  | GtOperation
  | Operation.LtOperation
  | GteOperation
  | Operation.LteOperation
  | InOperation
  | ContainsOperation;

export namespace Operation {
  /**
   * Less than comparison.
   *
   * Example:
   * ` { "$lt": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
   */
  export interface LtOperation {
    $lt: Array<unknown>;
  }

  /**
   * Less than or equal comparison.
   *
   * Example:
   * ` { "$lte": [{"$getField": "summary.usage.tokens"}, {"$literal": 100}] } `
   */
  export interface LteOperation {
    $lte: Array<unknown>;
  }
}

/**
 * Logical OR. At least one condition must be true.
 *
 * Example:
 * ` { "$or": [ {"$eq": [{"$getField": "op_name"}, {"$literal": "a"}]}, {"$eq": [{"$getField": "op_name"}, {"$literal": "b"}]} ] } `
 */
export interface OrOperation {
  $or: Array<Operation>;
}
