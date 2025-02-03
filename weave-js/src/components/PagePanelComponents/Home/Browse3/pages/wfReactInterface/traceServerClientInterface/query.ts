type LiteralOperation = {
  $literal:
    | string
    | number
    | boolean
    | {[key: string]: LiteralOperation}
    | LiteralOperation[];
};

type GetFieldOperator = {
  $getField: string;
};

type ConvertSpec = {
  input: Operand;
  to: 'double' | 'string' | 'int' | 'bool';
};

type ConvertOperation = {
  $convert: ConvertSpec;
};

type AndOperation = {
  $and: Operand[];
};

type OrOperation = {
  $or: Operand[];
};

type NotOperation = {
  $not: [Operand];
};

type EqOperation = {
  $eq: [Operand, Operand];
};

type GtOperation = {
  $gt: [Operand, Operand];
};

type InOperation = {
  $in: [Operand, Operand[]];
};

type GteOperation = {
  $gte: [Operand, Operand];
};

type ContainsSpec = {
  input: Operand;
  substr: Operand;
  case_insensitive?: boolean;
};

type ContainsOperation = {
  $contains: ContainsSpec;
};

type Operation =
  | AndOperation
  | OrOperation
  | NotOperation
  | EqOperation
  | GtOperation
  | GteOperation
  | InOperation
  | ContainsOperation;

type Operand =
  | LiteralOperation
  | GetFieldOperator
  | ConvertOperation
  | Operation;

export type Query = {
  $expr: Operation;
};
