import React from 'react';

import {AudioPlayer} from './Audio/AudioPlayer';
import {ContentView} from './Content/ContentView';
import {CustomWeaveTypePayload} from './customWeaveType.types';
import {DateTimeView} from './datetime.datetime/DateTimeView';
import {MarkdownView} from './Markdown/MarkdownView';
import {VideoPlayer} from './moviepy.video.VideoClip/VideoPlayer';
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
      mode?: string;
      data: any; // I wish this could be typed more specifically
    }>;
    preferredRowHeight?: number;
  };
} = {
  'PIL.Image.Image': {
    component: PILImageImage,
    preferredRowHeight: 350,
  },
  'PIL.JpegImagePlugin.JpegImageFile': {
    component: PILImageImage,
    preferredRowHeight: 350,
  },
  'PIL.PngImagePlugin.PngImageFile': {
    component: PILImageImage,
    preferredRowHeight: 350,
  },
  'wave.Wave_read': {
    component: AudioPlayer,
  },
  'weave.type_handlers.Audio.audio.Audio': {
    component: AudioPlayer,
  },
  'datetime.datetime': {
    component: DateTimeView,
  },
  'rich.markdown.Markdown': {
    component: MarkdownView,
    preferredRowHeight: 350,
  },
  'moviepy.video.VideoClip.VideoClip': {
    component: VideoPlayer,
  },
  'weave.type_wrappers.Content.content.Content': {
    component: ContentView,
  },
};

export const getCustomWeaveTypePreferredRowHeight = (
  typeId: string
): number | undefined => {
  return customWeaveTypeRegistry[typeId]?.preferredRowHeight;
};

/**
 * This context is used to provide the entity and project to the
 * CustomWeaveTypeDispatcher. Importantly, what this does is allows the
 * developer to inject an entity/project context around some component tree, and
 * then any CustomWeaveTypeDispatchers within that tree will be assumed to be
 * within that entity/project context. This is far cleaner than passing
 * entity/project down through the tree. We just have to remember in the future
 * case when we support multiple entities/projects in the same tree, we will
 * need to update this context if you end up traversing into a different
 * entity/project. This should already be accounted for in all the current
 * use-cases.
 */
export const CustomWeaveTypeProjectContext = React.createContext<{
  entity: string;
  project: string;
  mode?: string;
} | null>(null);

/**
 * This is the primary entry-point for dispatching custom weave types.
 */
export const CustomWeaveTypeDispatcher: React.FC<
  CustomWeaveTypeDispatcherProps
> = ({data, entity, project}) => {
  const projectContext = React.useContext(CustomWeaveTypeProjectContext);
  const typeId = data.weave_type.type;
  const comp = customWeaveTypeRegistry[typeId]?.component;
  const defaultReturn = <span>Custom Weave Type: {typeId}</span>;

  if (comp) {
    const applicableEntity = entity || projectContext?.entity;
    const applicableProject = project || projectContext?.project;
    if (applicableEntity == null || applicableProject == null) {
      console.warn(
        'CustomWeaveTypeDispatch: entity and project must be provided in context or as props'
      );
      return defaultReturn;
    }
    return React.createElement(comp, {
      entity: applicableEntity,
      project: applicableProject,
      mode: projectContext?.mode,
      data,
    });
  }

  return defaultReturn;
};
