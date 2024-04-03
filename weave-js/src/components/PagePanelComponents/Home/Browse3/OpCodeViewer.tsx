import React, {useState} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {Button} from '../../../Button';
import {Browse2OpDefCode} from '../Browse2/Browse2OpDefCode';
import {useWeaveflowCurrentRouteContext} from './context';
import {OpCodeViewerDiff} from './OpCodeViewerDiff';
import {opVersionKeyToRefUri} from './pages/wfReactInterface/utilities';
import {OpVersionSchema} from './pages/wfReactInterface/wfDataModelHooksInterface';
import {SelectOpVersion} from './SelectOpVersion';

type OpCodeViewerProps = {
  entity: string;
  project: string;
  opName: string;
  opVersions: OpVersionSchema[];

  // Op we are currently viewing, and will go back to if we exit diff mode.
  currentVersionURI: string;
};

type DiffState = {
  left: string | null;
  right: string | null;
};

const OpCodeViewerContainer = styled.div`
  height: 100%;
  display: flex;
  flex-direction: column;
`;
OpCodeViewerContainer.displayName = 'S.OpCodeViewerContainer';

const DiffBar = styled.div`
  padding: 8px;
`;
DiffBar.displayName = 'S.DiffBar';

const SelectVersionBar = styled.div`
  display: flex;
`;
SelectVersionBar.displayName = 'S.SelectVersionBar';

const VersionHeader = styled.div`
  display: flex;
  align-items: center;
  padding: 0 8px;
`;
VersionHeader.displayName = 'S.VersionHeader';

export const OpCodeViewer = ({
  entity,
  project,
  opName,
  opVersions,
  currentVersionURI,
}: OpCodeViewerProps) => {
  const routerContext = useWeaveflowCurrentRouteContext();
  const history = useHistory();

  const isDiffAvailable = opVersions.length > 1;
  const [diffState, setDiffState] = useState<DiffState>({
    left: null,
    right: null,
  });
  const uris = opVersions.map(opv => opVersionKeyToRefUri(opv));

  const onEnterDiff = () => {
    const i = uris.indexOf(currentVersionURI);
    if (i === 0) {
      setDiffState({left: uris[0], right: uris[1]});
    } else {
      setDiffState({left: uris[i - 1], right: uris[i]});
    }
  };
  const hasPrev = diffState.left && uris.indexOf(diffState.left) > 0;
  const hasNext =
    diffState.right && uris.indexOf(diffState.right) < uris.length - 1;
  const onPrevious = () => {
    const lIndex = uris.indexOf(diffState.left!);
    setDiffState({left: uris[lIndex - 1], right: uris[lIndex]});
  };
  const onNext = () => {
    const rIndex = uris.indexOf(diffState.right!);
    setDiffState({left: uris[rIndex], right: uris[rIndex + 1]});
  };
  const onSetLeft = (uri: string) => {
    setDiffState({left: uri, right: diffState.right});
  };
  const onSetRight = (uri: string) => {
    setDiffState({left: diffState.left, right: uri});
  };
  const onExitDiff = () => {
    setDiffState({left: null, right: null});
  };

  const openVersion = (uri: string) => {
    const opVersion = opVersions.find(opv => opVersionKeyToRefUri(opv) === uri);
    const hash = opVersion?.versionHash!;
    const url = routerContext.opVersionUIUrl(entity, project, opName, hash);
    history.push(url);
    onExitDiff();
  };
  const openLeft = () => {
    openVersion(diffState.left!);
  };
  const openRight = () => {
    openVersion(diffState.right!);
  };

  const [leftSize, setLeftSize] = useState('50%');
  const onSplitResize = (left: number) => {
    setLeftSize(left + 'px');
  };

  const opVersionsDesc = opVersions.slice().reverse();

  let diffBar = null;
  if (isDiffAvailable) {
    diffBar = diffState.left ? (
      <DiffBar>
        <Button
          disabled={!hasPrev}
          variant="secondary"
          icon="chevron-back"
          onClick={onPrevious}
          tooltip="Compare earlier versions"
        />
        <Button
          disabled={!hasNext}
          variant="secondary"
          icon="chevron-next"
          onClick={onNext}
          tooltip="Compare later versions"
        />
        <Button
          className="ml-4"
          variant="secondary"
          icon="close"
          onClick={onExitDiff}
          tooltip="Exit diff mode"
        />
      </DiffBar>
    ) : (
      <DiffBar>
        <Button variant="secondary" onClick={onEnterDiff}>
          Diff versions
        </Button>
      </DiffBar>
    );
  }

  return (
    <OpCodeViewerContainer>
      {diffBar}
      {diffState.left == null || diffState.right == null ? (
        <Browse2OpDefCode uri={currentVersionURI} />
      ) : (
        <>
          <SelectVersionBar>
            <VersionHeader style={{width: leftSize}}>
              <SelectOpVersion
                opVersions={opVersionsDesc}
                valueURI={diffState.left}
                currentVersionURI={currentVersionURI}
                onChange={uri => onSetLeft(uri)}
              />
              <Button
                className="ml-4"
                icon="forward-next"
                variant="ghost"
                tooltip="Open page for this version"
                onClick={openLeft}
              />
            </VersionHeader>
            <VersionHeader>
              <SelectOpVersion
                opVersions={opVersionsDesc}
                valueURI={diffState.right}
                currentVersionURI={currentVersionURI}
                onChange={uri => onSetRight(uri)}
              />
              <Button
                className="ml-4"
                icon="forward-next"
                variant="ghost"
                tooltip="Open page for this version"
                onClick={openRight}
              />
            </VersionHeader>
          </SelectVersionBar>
          <OpCodeViewerDiff
            left={diffState.left}
            right={diffState.right}
            onSplitResize={onSplitResize}
          />
        </>
      )}
    </OpCodeViewerContainer>
  );
};
