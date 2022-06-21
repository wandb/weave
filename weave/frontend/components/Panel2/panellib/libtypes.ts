import {
  isAssignableTo as globalIsAssignableTo,
  nDims,
  nullableTaggableValue,
  listObjectType,
  Type as GlobalType,
} from '@wandb/cg/browser/model/types';
import {ConvertibleToDataTableType} from '../PanelTable/tableType';
import {Spec as PanelTableMergeSpec} from '../PanelTableMerge';

export interface TypedInputHandler<T> {
  inputType: T;
  id: string;
}

export interface TypedInputConverter<T> {
  id: string;
  // TODO: This is a combination of type filter and converter. We could
  // have an inputType for the filtering part (we need more generic types
  // since inputType isn't concrete for these)
  convert(inputType: T): T | null;
}

export type TypedInputHandlerStack<
  T,
  H extends TypedInputHandler<T>,
  C extends TypedInputConverter<T>
> = H | (C & {inputType: T; child: TypedInputHandlerStack<T, H, C>});

export function _getTypeHandlerStacks<
  T,
  H extends TypedInputHandler<T>,
  C extends TypedInputConverter<T>
>(
  currentType: T,
  handlers: H[],
  converters: C[],
  isAssignableTo: (type: T, toType: T) => boolean,
  parentConverterId?: string,
  multiTableIsAncestor?: boolean
) {
  const typeDims = nDims(currentType as unknown as GlobalType);
  const objType =
    typeDims === 1
      ? nullableTaggableValue(
          listObjectType(
            nullableTaggableValue(currentType as unknown as GlobalType)
          )
        )
      : null;
  let result: Array<TypedInputHandlerStack<T, H, C>> = handlers.filter(ps => {
    // // custom logic to avoid rendering tables and plots for lists of lists and list of table files
    // if (ps.id === 'table' || ps.id === 'plot') {
    //   if (typeDims > 1) {
    //     return false;
    //   } else if (
    //     objType != null &&
    //     globalIsAssignableTo(objType, ConvertibleToDataTableType)
    //   ) {
    //     return false;
    //   }
    // }

    return isAssignableTo(currentType, ps.inputType);
  });

  for (const converter of converters) {
    if (
      (converter.id !== 'row' && converter.id === parentConverterId) ||
      (multiTableIsAncestor && converter.id === PanelTableMergeSpec.id) ||
      (parentConverterId === 'row' && converter.id === PanelTableMergeSpec.id)
    ) {
      continue;
    }
    const convertedType = converter.convert(currentType);
    if (convertedType != null) {
      let children: Array<TypedInputHandlerStack<T, H, C>> =
        _getTypeHandlerStacks(
          convertedType,
          handlers,
          converters,
          isAssignableTo,
          converter.id,
          multiTableIsAncestor || converter.id === PanelTableMergeSpec.id
        );

      // Only include maybe -> non-null handling items
      if (converter.id === 'maybe') {
        children = children.filter(child => {
          return !globalIsAssignableTo(
            'none',
            child.inputType as unknown as GlobalType
          );
        });
      }
      result = result.concat(
        children.map(handler => ({
          ...converter,
          inputType: currentType,
          child: {
            ...handler,
            inputType: convertedType,
          },
        }))
      );
    }
  }

  return result;
}
