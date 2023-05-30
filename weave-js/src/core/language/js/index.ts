import {EditingNode, Stack, Type} from '../../model';
// tslint:disable-next-line:no-circular-imports
import type {WeaveInterface} from '../../weaveInterface';
import {ExpressionResult, LanguageBinding} from '../types';
import {parseCG} from './parser';
import {nodeToString, typeToString} from './print';

export * from './parser';

export class JSLanguageBinding implements LanguageBinding {
  public constructor(private readonly weave: WeaveInterface) {}

  parse(input: string, stack?: Stack | undefined): Promise<ExpressionResult> {
    return parseCG(this.weave, input, stack ?? []);
  }

  printGraph(
    input: EditingNode<Type>,
    indent?: number | null | undefined
  ): string {
    return nodeToString(input, this.weave.client.opStore, indent);
  }

  printType(input: Type, simple?: boolean): string {
    return typeToString(input, simple);
  }
}
