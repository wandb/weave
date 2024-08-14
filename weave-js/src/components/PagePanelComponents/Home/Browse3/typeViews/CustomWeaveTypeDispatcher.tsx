import React from 'react';

import {CustomWeaveTypePayload} from './customWeaveType.types';
import {PILImageImage} from './PIL.Image.Image/PILImageImage';

type CustomWeaveTypeDispatcherProps = {
  data: CustomWeaveTypePayload;
  // Entity and Project can be optionally provided as props, but if they are not
  // provided, they must be provided in context. Failure to provide them will
  // result in a console warning and a fallback to a default component.
  //
  // This pattern is used because in many cases we are rendering data from
  // hierarchical data structures, and we want to avoid passing entity and project
  // down through the tree.
  entity?: string;
  project?: string;
};

const customWeaveTypeRegistry: {
  [typeId: string]: {
    component: React.FC<{
      entity: string;
      project: string;
      data: any; // I wish this could be typed more specifically
    }>;
  };
} = {
  'PIL.Image.Image': {
    component: PILImageImage,
  },
};

export const CustomWeaveTypeProjectContext = React.createContext<{
  entity: string;
  project: string;
} | null>(null);

/**
 * This is the primary entry-point for dispatching custom weave types. Currently
 * we just have 1, but as we add more, we might want to add a more robust
 * "registry"
 */
export const CustomWeaveTypeDispatcher: React.FC<
  CustomWeaveTypeDispatcherProps
> = ({data, entity, project}) => {
  const projectContext = React.useContext(CustomWeaveTypeProjectContext);
  const comp = maybeGetComponentForCustomWeaveTypeData(data);
  const defaultReturn = <span>Custom Weave Type: {data.weave_type.type}</span>;

  if (comp) {
    const useEntity = entity || projectContext?.entity;
    const useProject = project || projectContext?.project;
    if (useEntity == null || useProject == null) {
      console.warn(
        'CustomWeaveTypeDispatch: entity and project must be provided in context or as props'
      );
      return defaultReturn;
    }
    return React.createElement(comp, {
      entity: useEntity,
      project: useProject,
      data,
    });
  }

  return defaultReturn;
};

const maybeGetComponentForCustomWeaveTypeData = (
  data: CustomWeaveTypePayload
): React.FC<{
  entity: string;
  project: string;
  data: any;
}> | null => {
  const typeId = data.weave_type.type;
  const comp = customWeaveTypeRegistry[typeId];
  if (comp) {
    return comp.component;
  }

  return null;
};

// export const customWeaveTypeDataHasComponent = (
//   data: CustomWeaveTypePayload
// ): boolean => {
//   const typeId = data.weave_type.type;
//   const comp = customWeaveTypeRegistry[typeId];
//   if (comp) {
//     return true;
//   }

//   return false;
// };
