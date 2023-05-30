import type {EditingNode} from '../model/graph/editing/types';
import type {Stack} from '../model/graph/types';
import type {Type} from '../model/types';
import {StaticOpStore} from '../opStore/static';
import {nodeToString, typeToString} from './js/print';
import {ExpressionResult, LanguageBinding} from './types';

// Default language binding that does not support parsing (since it requires a weave interface)
// Technically incorrect for anything to depend on this class, as the static op store may
// not represent the true state of Weave, but provided as compatibility shim for existing
// use cases that depend on static nodeToString/typeToString functionality
class DefaultLanguageBinding implements LanguageBinding {
  parse(input: string, stack?: Stack): Promise<ExpressionResult> {
    throw new Error('Method not implemented.');
  }
  printGraph(input: EditingNode<Type>, indent?: number | null): string {
    return nodeToString(input, StaticOpStore.getInstance(), indent);
  }
  printType(input: Type, simple?: boolean): string {
    return typeToString(input, simple);
  }
}

export const defaultLanguageBinding = new DefaultLanguageBinding();
