import {mapValues, memoize, omit} from 'lodash';
import moment from 'moment';
import {performance} from 'universal-perf-hooks';
import Parser from 'web-tree-sitter';
// @ts-ignore
import treeSitterWasmUrl from 'web-tree-sitter/tree-sitter.wasm';

import {callOpVeryUnsafe, mapNodes} from '../../../callers';
import {getFunctionFrame, getPlaceholderArg} from '../../../hl';
import {
  constBoolean,
  constDate,
  constLink,
  constNumber,
  constString,
  nullableTaggableStrip,
} from '../../../model';
import {
  constNone,
  Frame,
  NodeOrVoidNode,
  OpInputs,
  pushFrame,
  resolveVar,
  Stack,
  varNode,
  voidNode,
} from '../../../model/graph';
import {
  EditingNode,
  EditingOpInputs,
  EditingOutputNode,
} from '../../../model/graph/editing';
import {
  isAssignableTo,
  isFunctionType,
  isList,
  isListLike,
  listObjectType,
  nullableTaggableValue,
} from '../../../model/helpers';
import {intersectionOf} from '../../../model/intersection';
import {Type} from '../../../model/types';
import {opArray, opDict, opNot, opNumberNegate} from '../../../ops';
import {OpDef} from '../../../opStore';
import {determineOutputType} from '../../../opStore/static';
import {getOpDefsByDisplayName} from '../../../opStore/util';
import {LOG_DEBUG_MESSAGES} from '../../../util/constants';
import {isWeaveDebugEnabled} from '../../../util/debug';
import type {WeaveInterface} from '../../../weaveInterface';
import {defaultLanguageBinding} from '../../default';
import {ExpressionResult} from '../../types';
import {typeToString} from '../print';
// @ts-ignore
import languageModuleUrl from './tree-sitter-weave.wasm';

export {Parser};

async function _getParser(): Promise<Parser | Parser> {
  await Parser.init({
    locateFile: (path: any, prefix: any) => {
      if (path === 'tree-sitter.wasm') {
        return treeSitterWasmUrl;
      }
      return `/${path}`;
    },
  });
  const parser = new Parser();
  const Lang = await Parser.Language.load(languageModuleUrl);
  parser.setLanguage(Lang);

  return parser;
}

const getParser = memoize(_getParser);

function logEvent(expr: EditingNode, label: string) {
  if (!isWeaveDebugEnabled()) {
    return;
  }

  let exprString = defaultLanguageBinding.printGraph(expr, null);
  if (exprString.length > 100) {
    exprString = exprString.slice(0, 40) + '...' + exprString.slice(-40);
  }
  console.debug(
    `[Weave] [${(performance.now() / 1000).toFixed(
      3
    )}s] ${label}: ${exprString}`
  );
}

export async function parseCG(
  weave: WeaveInterface,
  rawExpr: string,
  stack: Stack
): Promise<ExpressionResult> {
  const parser = await getParser();

  let parseResult: Parser.Tree | null = null;
  let exprResult: EditingNode = voidNode();
  const converter = new Converter(weave);

  try {
    parseResult = parser.parse(rawExpr);
  } catch (e) {
    if (LOG_DEBUG_MESSAGES) {
      console.warn('parse failure: ', (e as any).message);
    }
  }

  if (parseResult != null) {
    try {
      exprResult = await converter.tsTreeToCG(parseResult.rootNode, stack);
    } catch (e) {
      if (LOG_DEBUG_MESSAGES) {
        console.warn('conversion failure:', (e as any).message);
      }
    }
  }

  logEvent(exprResult, 'parser.final.refine');
  const refinedResult = await converter.refineNode(
    exprResult,
    stack,
    converter.refineCache
  );

  const nodeMap = new Map();
  const strippedResult = mapNodes(refinedResult, node => {
    const strippedNode = omit(node, ['__syntaxKeyRef']) as EditingNode;
    nodeMap.set(node.__syntaxKeyRef!, strippedNode);
    return strippedNode;
  });

  return {
    expr: strippedResult,
    parseTree: parseResult?.rootNode,
    nodeMap,
    extraText: converter.extraText,
  };
}

class Converter {
  public extraText: string | undefined;

  // Memoized...
  public tsTreeToCG: typeof this._tsTreeToCG;
  public readonly refineCache: Map<EditingNode, EditingNode>;

  public refineNode: typeof this.weave.refineEditingNode;

  public constructor(private readonly weave: WeaveInterface) {
    this.tsTreeToCG = memoize(this._tsTreeToCG.bind(this));

    const boundRefine = this.weave.refineEditingNode.bind(this.weave);
    this.refineCache = new Map();
    this.refineNode = (node, frame) =>
      boundRefine(node, frame, this.refineCache);
  }

  public async _tsTreeToCG(
    syntaxNode: Parser.SyntaxNode,
    stack: Stack,
    contextExpectedOutputType?: Type
  ): Promise<EditingNode> {
    const mapped = (node: EditingNode): Promise<EditingNode> =>
      this.record(syntaxNode, node);

    switch (syntaxNode.type) {
      // NOOPs (skipped)
      case 'program':
      case 'expression_statement':
      case 'parenthesized_expression':
        if (syntaxNode.firstNamedChild == null) {
          return mapped(voidNode());
        }
        return this.tsTreeToCG(
          syntaxNode.firstNamedChild,
          stack,
          contextExpectedOutputType
        );

      // Variables
      case 'identifier':
        const resolved = resolveVar(stack, syntaxNode.text);
        return mapped(
          varNode(resolved?.closure.value?.type ?? 'any', syntaxNode.text)
        );

      // Basic literals
      case 'number':
        return mapped(constNumber(Number(syntaxNode.text)));
      case 'string':
        // "some string" or 'some string' (n.b: quotes included!)
        return mapped(constString(stripQuotesAndUnescape(syntaxNode.text)));
      case 'true':
        return mapped(constBoolean(true));
      case 'false':
        return mapped(constBoolean(false));
      case 'null':
        return mapped(constNone());

      // Complex literals
      // Additional special cases are parsed as call_expressions
      case 'array': {
        // [ x, y, z, ... ]
        const inputNodes = syntaxNode.namedChildren;
        const arrValues = await Promise.all(
          inputNodes.map(el => this.tsTreeToCG(el, stack))
        );
        const arrInput = Object.fromEntries(
          inputNodes.map((node, ind) => [ind, arrValues[ind]])
        );
        return mapped(opArray(arrInput as any));
      }
      case 'object': {
        // { key: value, ... } or { 'key': value, ... }
        const pairs = syntaxNode.namedChildren;
        const pairValues = await Promise.all(
          pairs.map(el => {
            const valNode = el.namedChildren[1];
            return this.tsTreeToCG(valNode, stack);
          })
        );
        const dictInput = Object.fromEntries(
          pairs.map((pair, ind) => {
            const rawKey = pair.namedChildren[0].text;
            return [stripQuotesAndUnescape(rawKey), pairValues[ind]];
          })
        );
        return mapped(opDict(dictInput as any));
      }
      case 'arrow_function':
        // (x) => x
        const parameterTypes: {[name: string]: Type} = {};
        const parameterVars: Frame = {};

        const [params, body] = syntaxNode.namedChildren;

        for (const param of params.namedChildren || []) {
          if (param.type !== 'identifier') {
            throw new Error(
              `Invalid function argument: ${JSON.stringify(param)}`
            );
          }

          const paramName = param.text;

          // Deref variables if possible.  Required for nested functions
          // that potentially alias existing vars in frame.
          const resolvedNode = resolveVar(stack, paramName)?.closure.value;
          parameterTypes[paramName] =
            resolveVar(stack, paramName)?.closure.value?.type ?? 'any';
          parameterVars[paramName] = resolvedNode ?? varNode('any', paramName);
        }

        let expectedFunctionLiteralOutputType: Type | undefined;

        if (
          typeof contextExpectedOutputType === 'object' &&
          contextExpectedOutputType.type === 'function'
        ) {
          // an expected type was passed from the parse context -- this probably means
          // that this function literal is inside of an op, e.g.
          //
          // arr.filter((row) => row["boolProperty"])
          //
          // Above, we assigned type `any` to each parameter as a default. But because we
          // have this extra information about the function's expected type, we can override
          // those types with more specific ones.
          //
          expectedFunctionLiteralOutputType =
            contextExpectedOutputType.outputType;
          // TODO: this requires that the function literal uses the exact parameter names
          // specified by the op above. Ideally, it should handle any argument names and
          // use position to assign types instead.

          for (const paramName of Object.keys(parameterVars)) {
            const contextExpectedParamType =
              contextExpectedOutputType.inputTypes[paramName];
            if (
              contextExpectedParamType &&
              (parameterTypes[paramName] == null ||
                parameterTypes[paramName] === 'any')
            ) {
              parameterTypes[paramName] = contextExpectedParamType;
              parameterVars[paramName] = varNode(
                contextExpectedParamType,
                paramName
              );
            }
          }
        }

        const functionBodyStack = pushFrame(stack, parameterVars);

        const bodyNode = await this.tsTreeToCG(body, functionBodyStack);

        return mapped({
          nodeType: 'const',
          type: {
            type: 'function',
            inputTypes: parameterTypes,
            outputType: expectedFunctionLiteralOutputType || 'any',
          },
          val: bodyNode,
        });

      // Operators
      case 'unary_expression': {
        // !x
        const [unaryOp, value] = syntaxNode.children;
        switch (unaryOp.text) {
          case '-':
            return mapped(
              opNumberNegate({
                val: (await this.tsTreeToCG(value, stack)) as any,
              })
            );
          case '!':
            return mapped(
              opNot({
                bool: (await this.tsTreeToCG(value, stack)) as any,
              })
            );
          default:
            return mapped(voidNode());
        }
      }

      case 'binary_expression': {
        // x + y
        const [left, binaryOp, right] = syntaxNode.children;

        // handle a few alternate forms of operators -- they will get
        // rendered back to their standard forms when the expression is
        // stringified

        // TODO: might make sense to move these into a property on the op definition,
        // especially if we start to have a lot of them or they go beyond just binary
        // ops
        let convertedOp = binaryOp.text;
        switch (convertedOp) {
          case '&&':
            convertedOp = 'and';
            break;
          case '||':
            convertedOp = 'or';
            break;
          case '=':
          case '===':
            convertedOp = '==';
            break;
          case '!=':
          case '!==':
            convertedOp = '!=';
            break;
        }

        return mapped(
          await this.binaryExpression(stack, convertedOp, left, right)
        );
      }

      case 'call_expression': {
        // fn(x, y, ...)
        const [fnName, args] = syntaxNode.namedChildren;
        if (fnName.text === 'Date') {
          // Special case: Date("moment-compatible input string")
          const [dateInput] = args.namedChildren;
          return mapped(
            constDate(moment(stripQuotesAndUnescape(dateInput.text)).toDate())
          );
        }
        if (fnName.text === 'Link') {
          // Special case: Link("url","label")
          const [url, optionalLabel] = args.namedChildren;
          const label = (optionalLabel ?? url).text;
          return mapped(
            constLink(
              stripQuotesAndUnescape(label),
              stripQuotesAndUnescape(url.text)
            )
          );
        }

        return mapped(await this.callExpressionToCG(syntaxNode, stack));
      }

      // Property/element access
      case 'subscript_expression': {
        // x[y]
        const [obj, rawIndex] = syntaxNode.namedChildren;
        try {
          const pickResult = await this.buildOutputNodeFromNameAndArgs(
            stack,
            'pick',
            [obj, rawIndex],
            'brackets'
          );
          return mapped(pickResult);
        } catch (e) {
          if (e instanceof Error) {
            const indexResult = await this.buildOutputNodeFromNameAndArgs(
              stack,
              'index',
              [obj, rawIndex],
              'brackets'
            );
            return mapped(indexResult);
          }

          throw e;
        }
      }

      // op "method" or object attribute access
      case 'member_expression': {
        // x.y
        const [obj, property] = syntaxNode.namedChildren;

        try {
          const getAttrNode = callOpVeryUnsafe('Object-__getattr__', {
            self: await this.tsTreeToCG(obj, stack),
            name: await mapped(constString(property.text)),
          });

          logEvent(getAttrNode, 'parser.getattr.refine');
          const refinedNode = (await this.refineNode(
            getAttrNode,
            stack
          )) as EditingOutputNode;
          const refinedType = nullableTaggableValue(refinedNode.type);
          if (
            refinedType === 'unknown' ||
            (isListLike(refinedType) &&
              nullableTaggableValue(listObjectType(refinedType)) === 'unknown')
          ) {
            throw new Error(`Invalid getattr call`);
          }
          return mapped(getAttrNode);
        } catch (e) {
          // passthrough
        }

        try {
          const chainNode = await this.buildOutputNodeFromNameAndArgs(
            stack,
            property.text,
            [obj],
            'chain'
          );
          return mapped(chainNode);
        } catch (e) {
          // passthrough
        }

        this.extraText = '.' + property.text;
        return this.tsTreeToCG(obj, stack);
      }

      case 'ERROR': {
        // Apply some heuristics and try to handle some corner cases
        const {text, namedChildren} = syntaxNode;

        if (text === '.') {
          this.extraText = '.';
          return mapped(voidNode());
        }

        // Hanging dot: foo.
        if (
          text.length > 1 &&
          text.endsWith('.') &&
          namedChildren.length === 1
        ) {
          this.extraText = '.';
          return this.tsTreeToCG(
            namedChildren[0],
            stack,
            contextExpectedOutputType
          );
        }

        // Hanging square bracket: foo.summary[
        if (
          text.length > 1 &&
          text.endsWith('[') &&
          namedChildren.length === 1
        ) {
          this.extraText = '[';
          return this.tsTreeToCG(
            namedChildren[0],
            stack,
            contextExpectedOutputType
          );
        }

        // Hanging square bracket with opening quote and maybe some text?: foo.summary["
        if (text.length > 2 && namedChildren.length >= 1) {
          const validChild = namedChildren[0];
          const suffix = text.slice(validChild.text.length);
          if (suffix.match(/\[["'].*$/)) {
            this.extraText = suffix;
            return this.tsTreeToCG(
              namedChildren[0],
              stack,
              contextExpectedOutputType
            );
          }
        }

        // Hanging binary op?
        if (text.length > 1 && namedChildren.length === 1) {
          const validChild = namedChildren[0];
          const maybeOp = text.slice(validChild.text.length).trim();
          return mapped(
            await this.binaryExpression(stack, maybeOp, validChild)
          );
        }

        if (LOG_DEBUG_MESSAGES) {
          console.log(`Cannot recover ERROR node: ${syntaxNode.toString()}`);
        }
        return mapped(voidNode());
      }

      default:
        return mapped(voidNode());
    }
  }

  private record(
    syntaxNode: Parser.SyntaxNode,
    node: EditingNode
  ): Promise<EditingNode> {
    node.__syntaxKeyRef = syntaxNode.id;
    return Promise.resolve(node);
  }

  private async binaryExpression(
    stack: Stack,
    rawOp: string,
    left: Parser.SyntaxNode,
    right?: Parser.SyntaxNode
  ): Promise<EditingNode> {
    let convertedOp = rawOp;
    switch (convertedOp) {
      case '&&':
        convertedOp = 'and';
        break;
      case '||':
        convertedOp = 'or';
        break;
      case '=':
      case '===':
        convertedOp = '==';
        break;
      case '!=':
      case '!==':
        convertedOp = '!=';
        break;
    }

    return await this.buildOutputNodeFromNameAndArgs(
      stack,
      convertedOp,
      right ? [left, right] : [left],
      'binary'
    );
  }

  private async buildOutputNodeFromNameAndArgs(
    stack: Stack,
    displayName: string,
    args: Parser.SyntaxNode[],
    expectedRenderType: string
  ): Promise<EditingNode> {
    const arg0Node =
      args.length > 0 ? await this.tsTreeToCG(args[0], stack) : voidNode();
    const arg0Type = arg0Node.type;

    // In addition to display name, we can filter down to
    // the ops that have the expected render type and also
    // compatible (assignable) param for first arg (guaranteed to exist)
    const opDefs = getOpDefsByDisplayName(
      displayName,
      this.weave.client.opStore
    ).filter(opDef => {
      const param0Type = Object.values(opDef.inputTypes)[0] ?? 'invalid';
      return (
        opDef.renderInfo.type === expectedRenderType &&
        this.weave.typeIsAssignableTo(arg0Type, param0Type)
      );
    });

    if (opDefs.length === 0) {
      throw new Error(
        `Call to unknown ${expectedRenderType} op ${displayName} for type ${this.weave.typeToString(
          arg0Type
        )}`
      );
    }

    // many ops have the same display name,
    // so we may have more than one match
    // e.g. 'user' matches both user() and run.user()

    const possibleCalls = await Promise.all(
      opDefs.map(async opDef => {
        // the easiest way to distinguish between the matching ops is to
        // make a tree where we call each one...

        const parsedArgs = await Promise.all(
          args.map(async (arg, i) => {
            if (arg.type === 'arrow_function') {
              // this argument is a function literal, which means we'll need to use
              // type information from the op to decide what its inputs and return type
              // should be

              let expectedFunctionType = Object.values(opDef.inputTypes)[i];

              if (!isFunctionType(expectedFunctionType)) {
                // the user has entered a function where another type was expected
                // this will be an invalid expression in the end, but we may as well
                // refine the types inside the function to the extent that we can,
                // since doing so might help for editing
                return await this.tsTreeToCG(arg, stack, expectedFunctionType);
              }

              // now we're going to build the Node representing the function body --
              // i.e., the return value

              // to do that, we'll need to create a more specific version of the function
              // type that includes the TYPED variables that will be passed into the function:
              const functionParametersFrame = getFunctionFrame(
                opDef.name,
                await this.tsTreeToCG(args[0], stack),
                stack,
                this.weave.client.opStore
              );

              const expectedInputTypes = mapValues(
                functionParametersFrame,
                expectedParamNode => expectedParamNode.type
              );
              expectedFunctionType = {
                ...expectedFunctionType,
                inputTypes: expectedInputTypes,
              };

              let functionBodyGivenOpDef: NodeOrVoidNode;

              try {
                functionBodyGivenOpDef = (await this.tsTreeToCG(
                  arg,
                  pushFrame(stack, functionParametersFrame),
                  expectedFunctionType
                )) as NodeOrVoidNode;
              } catch (e) {
                functionBodyGivenOpDef = voidNode();
              }

              return functionBodyGivenOpDef;
            }

            return this.tsTreeToCG(arg, stack);
          })
        );

        const inputs = argsAsOpInputs(opDef, parsedArgs);
        const rawNode = callOpVeryUnsafe(
          opDef.name,
          inputs,
          determineOutputType(opDef, inputs as OpInputs)
        );

        if (LOG_DEBUG_MESSAGES) {
          console.log(`Converter: Refining node for better types`, rawNode);
        }
        let refinedNode: EditingNode = voidNode();
        try {
          logEvent(rawNode, 'parser.dispatch.refine');
          refinedNode = (await this.refineNode(
            rawNode,
            stack
          )) as EditingOutputNode;
        } catch (err) {
          console.warn(
            `Converter: Weave parser failed to refine node`,
            rawNode,
            err
          );
        }

        return refinedNode;
      })
    );

    if (LOG_DEBUG_MESSAGES) {
      console.log(`Converter: Possible calls`, possibleCalls);
    }

    // ...and then filter out any whose types are invalid -- that is, where
    // the types of the provided args couldn't be assigned to the inputs of
    // the op
    let validCalls: EditingOutputNode[] = possibleCalls.filter(
      node => node.type !== 'invalid'
    ) as any;

    if (validCalls.length === 0) {
      throw new Error(
        `Invalid call to op ${displayName}: args are invalid:
  ${args.map(arg => `${arg.text} (${arg.type})`).join('\n  ')} `
      );
    }

    if (validCalls.length > 1) {
      // Hack: x - y doesn't work because it is ambiguous with unary - (negation)
      if (displayName === '-') {
        return validCalls.find(call => call.fromOp.name === 'number-sub')!;
      }

      const possibleOps = validCalls.map(c =>
        this.weave.client.opStore.getOpDef(c.fromOp.name)
      );

      if (LOG_DEBUG_MESSAGES) {
        console.warn(
          `Converter: Ambiguous call to op ${displayName}: ${possibleOps
            .map(opDef => opDef.name)
            .join(', ')}\n`,
          `Intersection: ${typeToString(
            possibleOps.slice(1).reduce((memo, element) => {
              const firstArgType = Object.values(element.inputTypes)[0];
              return intersectionOf(memo, firstArgType);
            }, Object.values(possibleOps[0].inputTypes)[0]),
            false
          )}`
        );

        console.warn(
          `Converter: First arg types:\n${possibleOps
            .map(opDef => {
              const [firstArgName, firstArgType] = Object.entries(
                opDef.inputTypes
              )[0];
              return `  ${opDef.name}.${firstArgName}: ${typeToString(
                firstArgType,
                false,
                1
              )}`;
            })
            .join(' |\n')})`
        );

        console.warn(
          `Converter: Received type: ${typeToString(
            Object.values(validCalls[0].fromOp.inputs)[0].type,
            false
          )}`
        );
      }

      // HACKS to manually correct known edge cases :(

      const opChoices = validCalls.map(call => call.fromOp.name);
      if (LOG_DEBUG_MESSAGES) {
        console.warn(`opChoices = `, opChoices);
      }
      if (
        opChoices.length === 2 &&
        opChoices.includes('file-table') &&
        opChoices.includes('panel-table')
      ) {
        // 1. If it's file-table vs panel-table, let's pick file-table
        validCalls = validCalls.filter(
          call => call.fromOp.name === 'file-table'
        );
        if (LOG_DEBUG_MESSAGES) {
          console.warn(`Converter: Picking file-table over panel-table`);
        }
      } else {
        // Still ambiguous, let's filter out mapped ops and check again...
        const validCallsNoMapped = validCalls.filter(
          call =>
            !isMappedOpForInput(
              this.weave.client.opStore.getOpDef(call.fromOp.name),
              arg0Type
            )
        );
        if (validCallsNoMapped.length > 0) {
          if (LOG_DEBUG_MESSAGES) {
            console.warn(
              `Converter: Valid calls without mapped ops`,
              validCallsNoMapped
            );
          }
          validCalls = validCallsNoMapped;
        }

        if (validCalls.length > 1) {
          if (LOG_DEBUG_MESSAGES) {
            console.warn(
              'Converter: op dispatch is still ambiguous after removing mapped ops',
              validCalls
            );
          }
          // Still ambiguous, let's filter out tag getters and try again
          const validCallsNoTagGetters = validCalls.filter(
            call =>
              !isTagGetterOp(
                this.weave.client.opStore.getOpDef(call.fromOp.name)
              )
          );
          if (validCallsNoTagGetters.length > 0) {
            if (LOG_DEBUG_MESSAGES) {
              console.warn(
                `Converter: Valid calls without tag getters`,
                validCallsNoTagGetters
              );
            }
            validCalls = validCallsNoTagGetters;
          }
          if (validCalls.length > 1) {
            if (LOG_DEBUG_MESSAGES) {
              console.warn(
                'Converter: op dispatch is still ambiguous after removing tag getter ops',
                validCalls
              );
            }
          } else {
            if (LOG_DEBUG_MESSAGES) {
              console.warn(
                `Converter: Ambiguous op dispatch resolved by excluding tag-getter ops (choosing ${validCalls[0].fromOp.name})`
              );
            }
          }
        } else {
          if (LOG_DEBUG_MESSAGES) {
            console.warn(
              `Converter: Ambiguous op dispatch resolved by excluding mapped ops (choosing ${validCalls[0].fromOp.name})`
            );
          }
        }
      }
    }

    return validCalls[0];
  }

  private async callExpressionToCG(
    call: Parser.SyntaxNode,
    stack: Stack
  ): Promise<EditingNode> {
    const [fn, args] = call.namedChildren;

    if (fn.type === 'identifier') {
      // someOp()
      return this.buildOutputNodeFromNameAndArgs(
        stack,
        fn.text,
        args.namedChildren,
        'function'
      );
    } else if (fn.type === 'member_expression') {
      // obj.chainedOp()
      const [obj, chainedOp] = fn.namedChildren;
      if (chainedOp.type !== 'property_identifier') {
        throw new Error(
          `Invalid call: chained operator must be a property_identifier, but was ${JSON.stringify(
            chainedOp
          )}`
        );
      }

      return this.buildOutputNodeFromNameAndArgs(
        stack,
        fn.lastNamedChild!.text,
        [obj, ...args.namedChildren],
        'chain'
      );
    }

    return voidNode();
  }
}

function argsAsOpInputs(opDef: OpDef, args: EditingNode[]): EditingOpInputs {
  const argNames = Object.keys(opDef.inputTypes);
  return Object.fromEntries(
    argNames.map((name, i) => {
      return [
        name,
        args[i] ?? getPlaceholderArg(opDef, name) ?? varNode('any', ''),
      ];
    })
  );
}

function stripQuotesAndUnescape(input: string): string {
  const quotesStripped = ['"', "'"].includes(input[0])
    ? input.slice(1, -1)
    : input;
  return quotesStripped.replace(/\\"/g, '"');
}

// An op is "mapped for the input" if the input is list-like and the op
// can handle the list's object type.
function isMappedOpForInput(op: OpDef, firstArgType: Type): boolean {
  const firstInputType = Object.values(op.inputTypes)[0];
  const strippedArgType = nullableTaggableStrip(firstArgType);
  return (
    isList(strippedArgType) &&
    isAssignableTo(listObjectType(strippedArgType), firstInputType)
  );
}

function isTagGetterOp(op: OpDef): boolean {
  return op.kind === 'tag-getter';
}
