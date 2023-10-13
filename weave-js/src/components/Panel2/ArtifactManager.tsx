import {LegacyWBIcon} from '@wandb/weave/common/components/elements/LegacyWBIcon';
import {
  constString,
  findChainedAncestors,
  opRef,
  opRefBranchPoint,
} from '@wandb/weave/core';
import React, {useCallback, useMemo, useState} from 'react';

import {parseRef, useNodeValue} from '../../react';
import {getFullChildPanel} from './ChildPanel';
import {usePanelRenderedConfigByPath} from './PanelRenderedConfigContext';
import {isGroupNode, PanelTreeNode} from './panelTree';

const getAllArtifacts = (node: PanelTreeNode): string[] => {
  // console.log('GET ALL ART', node);
  if (isGroupNode(node)) {
    if (node.config == null) {
      return [];
    }
    return Object.values(node.config.items).flatMap(getAllArtifacts);
  }
  const full = getFullChildPanel(node);
  const chainNodes = findChainedAncestors(full.input_node as any, n => true);
  // console.log('CHAIN NODES', chainNodes);
  if (
    chainNodes.length > 0 &&
    chainNodes[0].nodeType === 'output' &&
    chainNodes[0].fromOp.name === 'get' &&
    chainNodes[0].fromOp.inputs.uri.nodeType === 'const'
  ) {
    // console.log('FOUND GET', chainNodes[0]);
    return [chainNodes[0].fromOp.inputs.uri.val];
  }
  return [];
};

export const ObjectEditStatus: React.FC<{artRef: string}> = ({artRef}) => {
  const branchPointNode = useMemo(
    () =>
      opRefBranchPoint({
        ref: opRef({uri: constString(artRef)}),
      }),
    [artRef]
  );
  // console.log('BRANCH POINT NODE', branchPointNode);
  const branchPoint = useNodeValue(branchPointNode).result;
  // console.log('BRANCH POINT', branchPoint);
  const parsed = parseRef(artRef);
  return (
    <div>
      {branchPoint != null ? (
        <div>
          {parsed.artifactName}:{branchPoint.branch} {' ← '}
          {parsed.artifactVersion} ({branchPoint.n_commits})
        </div>
      ) : (
        <div>
          {parsed.artifactName}:{parsed.artifactVersion}
        </div>
      )}
    </div>
  );
};

export const ArtifactManager: React.FC<{}> = React.memo(({children}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const renderedConfig = usePanelRenderedConfigByPath([]);
  const allArtRefs = useMemo(
    () => getAllArtifacts(renderedConfig),
    [renderedConfig]
  );
  const onMouseEnter = useCallback(() => setHovered(true), []);
  const onMouseLeave = useCallback(() => setHovered(false), []);
  // console.log('RENDERED CONFIG', renderedConfig, allArtRefs);
  const height = isOpen ? 300 : hovered ? 40 : 36;
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        width: 250,
        height,
        padding: '0 10px',
        border: '1px solid #eee',
        boxShadow: '0 0 10px rgba(0, 0, 0, 0.2)',
        backgroundColor: '#fff',
        zIndex: 100000,
        transition: 'height 0.2s',
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}>
      <div
        style={{
          height: 36,
          zIndex: 100000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
        }}
        onClick={() => setIsOpen(open => !open)}>
        <LegacyWBIcon title="" name="handle" />
      </div>
      <div
        style={{display: 'flex', justifyContent: 'center', marginBottom: 16}}>
        Objects
      </div>
      {isOpen &&
        allArtRefs.map(art => <ObjectEditStatus key={art} artRef={art} />)}
    </div>
  );
});
