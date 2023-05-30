import React, {FC} from 'react';

import {ControlsImageOverlays} from './ControlImageOverlays';
import * as Controls from './controlsImage';
import * as Panel2 from './panel';

const inputType = {
  type: 'dict' as const,
  objectType: {type: 'image-file' as const},
};

export interface PanelImageCompareConfigType {
  overlayControls?: Controls.OverlayControls;
}

type PanelImageCompareProps = Panel2.PanelProps<
  typeof inputType,
  PanelImageCompareConfigType
>;

const PanelImageCompareConfig: FC<PanelImageCompareProps> = ({
  context,
  config,
  updateConfig,
}) => {
  if (context.classSets == null) {
    throw new Error('Error: Class sets not loaded (PanelImageCompareConfig)');
  }

  return (
    <ControlsImageOverlays
      controls={config?.overlayControls}
      classSets={context.classSets}
      updateControls={updateConfig}
    />
  );
};

const PanelImageCompare: FC<PanelImageCompareProps> = props => {
  // TODO
  return <div>Image compare</div>;
  // const {context, updateContext, config, updateConfig} = props;

  // const overlayControls = useMemo(() => config.overlayControls ?? {}, [
  //   config.overlayControls,
  // ]);
  // const setMaskControls = useCallback(
  //   (controlId: string, control: Controls.OverlayState) =>
  //     updateConfig({
  //       overlayControls: {...overlayControls, [controlId]: control},
  //     }),
  //   [overlayControls, updateConfig]
  // );
  // const setClassSet = useCallback(
  //   (classSetId: string, classSet: Controls.ClassSetState) =>
  //     updateContext({
  //       classSets: {...context.classSets, [classSetId]: classSet},
  //     }),
  //   [context.classSets, updateContext]
  // );
  // const loadedImages = useMemo(() => {
  //   return props.input.map((entry, i) => ({
  //     loadedFrom: QueryPathUtil.toArtifactPath(entry.path),
  //     image: entry.value,
  //   }));
  // }, [props.input]);
  // const {
  //   loading: controlsLoading,
  //   maskControlsIDs,
  //   boxControlsIDs,
  // } = Controls.useWBImageControls(
  //   loadedImages,
  //   overlayControls,
  //   context.classSets,
  //   setMaskControls,
  //   setClassSet,
  //   false
  // );

  // if (controlsLoading) {
  //   return <div>loading</div>;
  // }

  // const anyNull = props.input.filter(i => i == null).length > 0;
  // const nonNull = props.input
  //   .map(({value: image}) => image)
  //   .filter(Obj.notEmpty);

  // const cantOverlay =
  //   anyNull ||
  //   nonNull.filter(
  //     p =>
  //       // TODO: (.digest is not a valid field on a wb-image object, yet we have it
  //       // in our type, we should get all these digests from the manifests instead
  //       // of duplicating them into wandb media object json)
  //       p.digest !== nonNull[0].digest ||
  //       p.classes?.digest !== nonNull[0].classes?.digest
  //   ).length > 0;

  // if (cantOverlay) {
  //   return (
  //     <div>
  //       {props.input.map(({value: image, key: name, path}, i) =>
  //         image == null ? (
  //           <div>{name}: null</div>
  //         ) : (
  //           <div style={{width: 240}}>
  //             {name}
  //             <CardImage
  //               image={{
  //                 path: {
  //                   ...QueryPathUtil.toArtifactPath(path),
  //                   path: image.path,
  //                 },
  //                 width: image.width,
  //                 height: image.height,
  //               }}
  //               boundingBoxes={
  //                 image.boxes != null ? Object.values(image.boxes) : undefined
  //               }
  //               masks={
  //                 image.masks != null
  //                   ? Object.values(image.masks).map(m => ({
  //                       ...QueryPathUtil.toArtifactPath(path),
  //                       path: m.path,
  //                     }))
  //                   : undefined
  //               }
  //               classSets={context.classSets}
  //               maskControls={
  //                 maskControlsIDs[i].map(id => overlayControls[id]) as any
  //               }
  //               boxControls={
  //                 boxControlsIDs[i].map(id => overlayControls[id]) as any
  //               }
  //             />
  //           </div>
  //         )
  //       )}
  //     </div>
  //   );
  // }

  // const image0 = props.input[0].value;

  // return image0 != null ? (
  //   <div style={{width: 240}}>
  //     <div>
  //       {props.input.map(({value: image, key: name, path}, i) => (
  //         <span>
  //           {name}
  //           {i !== props.input.length - 1 ? ', ' : ''}
  //         </span>
  //       ))}
  //     </div>
  //     <CardImage
  //       image={{
  //         path: {
  //           ...QueryPathUtil.toArtifactPath(props.input[0].path),
  //           path: image0.path,
  //         },
  //         width: image0.width,
  //         height: image0.height,
  //       }}
  //       boundingBoxes={props.input.flatMap(({value: image}) =>
  //         image?.boxes != null ? Object.values(image.boxes) : []
  //       )}
  //       masks={props.input.flatMap(({key: name, value: image, path}, i) =>
  //         image?.masks != null
  //           ? Object.values(image.masks).map(m => ({
  //               ...QueryPathUtil.toArtifactPath(path),
  //               path: m.path,
  //             }))
  //           : []
  //       )}
  //       classSets={context.classSets}
  //       maskControls={
  //         (config.overlayControls != null
  //           ? maskControlsIDs.flatMap(ids => ids.map(id => overlayControls[id]))
  //           : []) as any
  //       }
  //       boxControls={
  //         (config.overlayControls != null
  //           ? boxControlsIDs.flatMap(ids => ids.map(id => overlayControls[id]))
  //           : []) as any
  //       }
  //     />
  //   </div>
  // ) : (
  //   <div>null</div>
  // );
};

export const Spec: Panel2.PanelSpec = {
  id: 'image-file-compare',
  displayName: 'Image Compare',
  ConfigComponent: PanelImageCompareConfig,
  Component: PanelImageCompare,
  inputType,
};
