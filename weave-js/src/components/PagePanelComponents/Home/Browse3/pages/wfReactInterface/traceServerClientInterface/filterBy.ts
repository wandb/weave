type RawValue =
  | string
  | number
  | boolean
  | {[key: string]: RawValue}
  | RawValue[];
interface FieldSelect {
  field_: string;
  cast_?: 'str' | 'int' | 'float' | 'bool';
}
type Operand = RawValue | FieldSelect | Operation;
interface AndOperation {
  and_: [Operand, Operand];
}
interface OrOperation {
  or_: [Operand, Operand];
}
interface NotOperation {
  not_: Operand;
}
interface EqOperation {
  eq_: [Operand, Operand];
}
interface GtOperation {
  gt_: [Operand, Operand];
}
interface GteOperation {
  gte_: [Operand, Operand];
}
interface LikeOperation {
  like_: [Operand, Operand];
}
type Operation =
  | AndOperation
  | OrOperation
  | NotOperation
  | EqOperation
  | GtOperation
  | GteOperation
  | LikeOperation;

export interface FilterBy {
  filter: Operation;
}
