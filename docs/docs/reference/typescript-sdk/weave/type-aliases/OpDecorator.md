[**weave**](../README.md)

***

[weave](../README.md) / OpDecorator

# Type Alias: OpDecorator\<T\>

> **OpDecorator**\<`T`\> = (`value`, `context`) => `T` \| `void` & (`target`, `propertyKey`, `descriptor`) => `TypedPropertyDescriptor`\<`T`\> \| `void`

Defined in: [opType.ts:41](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/opType.ts#L41)

Helper type for decorators
This represents a decorator function that can be used with both legacy and Stage 3 decorators.

For Stage 3 decorators:
  target: The function being decorated (T)
  context: MethodDecoratorContext

For legacy decorators:
  target: The prototype (instance methods) or constructor (static methods)
  propertyKey: The method name
  descriptor: The property descriptor containing the method

## Type Parameters

### T

`T` *extends* (...`args`) => `any`
