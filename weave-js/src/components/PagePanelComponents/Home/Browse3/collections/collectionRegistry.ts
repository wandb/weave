import {
  ActionDispatchFilterSchema,
  ActionDefinitionSchema,
} from './actionCollection';

export const collectionRegistry = {
  ActionDefinition: ActionDefinitionSchema,
  ActionDispatchFilter: ActionDispatchFilterSchema,
};
