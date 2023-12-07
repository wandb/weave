import * as globals from '@wandb/weave/common/css/globals.styles';
import React from 'react';
import styled from 'styled-components';

// import {useWeaveContext} from '../../../../../context';
// import {constString, opGet} from '../../../../../core';
// import {PagePanelControlContextProvider} from '../../../../PagePanelContext';
// import {
//   CHILD_PANEL_DEFAULT_CONFIG,
//   ChildPanel,
//   ChildPanelFullConfig,
// } from '../../../../Panel2/ChildPanel';
// import {PanelInteractContextProvider} from '../../../../Panel2/PanelInteractContext';
// import {PanelRenderedConfigContextProvider} from '../../../../Panel2/PanelRenderedConfigContext';
// import {CenteredAnimatedLoader} from './common/Loader';
import {UnderConstruction} from './common/UnderConstruction';

const WeaveRoot = styled.div`
  position: absolute;
  top: 64px;
  bottom: 0;
  left: 240px;
  right: 0;
  background-color: ${globals.WHITE};
  color: ${globals.TEXT_PRIMARY_COLOR};
`;
WeaveRoot.displayName = 'S.WeaveRoot';

export const BoardPage: React.FC<{
  entity: string;
  project: string;
  boardId: string;
  versionId?: string;
}> = props => {
  return (
    <UnderConstruction
      title="Board"
      message={<>This page will contain an editable board</>}
    />
  );
  // const expString = `get("wandb-artifact:///${props.entity}/${props.project}/${
  //   props.boardId
  // }:${props.versionId ?? 'latest'}/obj")`;
  // const weave = useWeaveContext();
  // const [config, setConfig] = useState<ChildPanelFullConfig>(
  //   CHILD_PANEL_DEFAULT_CONFIG
  // );
  // const updateConfig = useCallback(
  //   (newConfig: Partial<ChildPanelFullConfig>) => {
  //     setConfig(currentConfig => ({...currentConfig, ...newConfig}));
  //     // if (newConfig.input_node != null) {
  //     //   setUrlExp(newConfig.input_node);
  //     // }
  //   },
  //   [setConfig]
  // );
  // const [loading, setLoading] = useState(true);
  // const transparentlyMountExpString = useRef('');
  // useEffect(() => {
  //   const doTransparently =
  //     expString != null && transparentlyMountExpString.current === expString;
  //   setLoading(!doTransparently);
  //   if (expString != null) {
  //     weave.expression(expString, []).then(res => {
  //       if (doTransparently) {
  //         updateConfig({
  //           input_node: res.expr as any,
  //         });
  //       } else {
  //         updateConfig({
  //           input_node: res.expr as any,
  //           id: '',
  //           config: undefined,
  //         } as any);
  //       }
  //       setLoading(false);
  //     });
  //   } else {
  //     setLoading(false);
  //   }
  //   // eslint-disable-next-line react-hooks/exhaustive-deps
  // }, [expString]);
  // if (loading) {
  //   return <CenteredAnimatedLoader />;
  // }
  // return (
  //   <PanelRenderedConfigContextProvider>
  //     <PanelInteractContextProvider>
  //       <WeaveRoot className="weave-root">
  //         <PagePanelControlContextProvider>
  //           <ChildPanel
  //             config={config}
  //             updateConfig={(newConfig: ChildPanelFullConfig<any>) => {
  //               // throw new Error('Function not implemented.');
  //             }}
  //           />
  //         </PagePanelControlContextProvider>
  //       </WeaveRoot>
  //     </PanelInteractContextProvider>
  //   </PanelRenderedConfigContextProvider>
  // );
};
