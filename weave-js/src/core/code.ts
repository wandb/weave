import {EditingNode} from './model';

// An expression is a node with the extra rule that its input graph may not
// have worked paths (ie it is tree-like). Its root are variables or consts.
// interface Expression {
//   node: LL.Node;
// }

// interface Assignment {
//   var: LL.VarNode;
//   expr: Expression;
// }

// Note this is the same as an assignment
export interface Assignment {
  name: string;
  node: EditingNode;
}

export interface CodeBlock {
  statements: Assignment[];
}

export function newCodeBlock(): CodeBlock {
  return {statements: []};
}

// function declareFunc<IT extends LL.InputTypes, OT extends Types.Type>(
//   name: string,
//   inputTypes: IT,
//   outputType: OT,
//   body: (inputs: LL.OpInputTypes<IT>) => LL.OutputNode<OT>
// ): {
//   // X
// };

// declareFunc('inc', {a: 'number'}, 'number', inputs => {
//   return LL.opNumberSub({lhs: inputs.a, rhs: LL.constNumber(1)});
// });
// // How to declare a function in our own code
// // func(inputSpec, outputType, (inputs) => {
// //
// // });
