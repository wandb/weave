import * as globals from '@wandb/weave/common/css/globals.styles';
import {Tab} from 'semantic-ui-react';
import styled from 'styled-components';

export const LCTDetailView = styled.div`
  flex: 1 1 auto;
  height: 50%;
`;

export const LCTTableSection = styled.div`
  flex: 1 1 auto;
  height: 50%;
`;

export const LCTWrapper = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;

export const SimpleTabs = styled(Tab)`
  display: flex;
  flex-direction: column;
  border-top: none;
  height: 100%;
  width: 100%;
  overflow: hidden;
  flex: 1 1 50px;
  .ui.tabular.menu {
    background-color: #fff;
    flex: 0 0 39px;
    padding: 0px;
    border-top: none;
    font-size: 16px;
    min-height: fit-content;
    max-width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    &::-webkit-scrollbar {
      display: none;
    }
    > .item {
      position: relative;
      opacity: 0.95;
      transition: none;
      background-color: none;
      border: none;
      .icon {
        margin-top: 4px;
      }
      /* If there's an ellispis menu, make it fit nicely */
      > .dropdown.icon > i.icon {
        width: auto;
        margin-left: 24px;
        margin-right: 0;
      }
      border-bottom: 2px solid transparent;
    }
    > .item,
    > .active.item {
      margin-bottom: 0;
      /* color: @gray700; */
      cursor: pointer;
      font-weight: normal;
      padding: 12px 16px 11px;
      margin-right: 10px;
      background: none;
      .label {
        /* color: @gray500; */
        background-color: white;
        font-size: 18px;
        margin-left: 8px;
        padding: 1px 3px;
      }
    }
    > .active.item {
      color: black;
      border-bottom: 2px solid #2e78c7;
    }
  }
`;

export const TabWrapper = styled.div`
  height: 100%;
  width: 100%;
  flex: 1 1 50px;
  overflow: hidden;
  padding-top: 16px;
  background-color: #fff;
`;

export const ConstrainedTextField = styled.div`
  max-height: 100px;
  overflow-y: auto;
`;

export const ModelWrapper = styled.div`
  width: 100%;
  height: 100%;
  overflow: auto;
  background-color: #fff;
`;

type ModelComponentProps = {
  backgroundColor: string;
  color: string;
};
export const ModelComponentHeader = styled.div<ModelComponentProps>`
  font-weight: bold;
  background-color: ${props => props.backgroundColor};
  color: ${props => props.color};
  width: 100%;
  line-height: 26px;
  text-align: left;
  padding: 2px 8px;
  border-radius: 4px;
  margin: 2px 0;
  font-size: 14px;
`;

export const KVTValue = styled.div`
  width: 100%;
  text-align: left;
  flex: 1 1 auto;
`;

type KVTValueProps = {
  isArrayItem: boolean;
};
export const KVTKey = styled.div<KVTValueProps>`
  width: ${props => (props.isArrayItem ? '25px' : '150px')};
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 0 0 auto;
  font-weight: bold;
  text-align: left;
`;

export const KVTRow = styled.div`
  display: flex;
  flex-direction: row;
  align-items: left;
  justify-content: left;
  width: 100%;
`;

export const KVTCollapseButton = styled.div`
  cursor: pointer;
  position: relative;
  top: -29px;
  left: calc(100% - 30px);
  height: 0px;
  color: #8f8f8fa6;
`;

type KVTWrapperProps = {
  canBeCollapsed: boolean;
};
export const KVTHeader = styled.div<KVTWrapperProps>`
  cursor: ${props => (props.canBeCollapsed ? 'pointer' : 'default')};
  width: 100%;
`;

export const KVTWrapper = styled.div`
  width: 100%;
`;

export const SpanElementChildSpanWrapper = styled.div`
  display: flex;
  flex-direction: row;
  gap: 2px;
`;

export const SpanElementChildSpansWrapper = styled.div`
  /* display: flex;
  flex-direction: row; */
`;

type SpanElementHeaderProps = {
  hasError: boolean;
  isSelected: boolean;
  backgroundColor: string;
  color: string;
};
export const SpanElementHeader = styled.div<SpanElementHeaderProps>`
  border: ${props =>
    props.hasError
      ? props.isSelected
        ? '1px solid red'
        : '1px dashed red'
      : props.isSelected
      ? '1px solid black'
      : '1px solid white'};
  background-color: ${props => props.backgroundColor};
  color: ${props => props.color};
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: bold;
  line-height: 26px;
  text-align: left;
  border-radius: 4px;
  font-size: 14px;
`;

export const SpanElementInner = styled.div`
  padding: 2px 8px;
  display: flex;
  justify-content: space-between;
`;

type SpanParentConnectorProps = {
  backgroundColor: string;
};
export const SpanParentConnector = styled.div<SpanParentConnectorProps>`
  background-color: ${props => props.backgroundColor};
`;

export const SpanDetailTable = styled.table`
  width: 100%;
`;

export const DurationLabel = styled.div`
  color: #8f8f8fa6;
`;

export const SpanDetailHeader = styled.div`
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background-color: #f6f6f6;
  color: black;
  font-weight: bold;
  line-height: 26px;
  text-align: left;
  padding: 2px 8px;
  border-radius: 4px;
  margin: 2px 0;
  font-size: 14px;
  display: flex;
  justify-content: space-between;
`;

export const SpanDetailWrapper = styled.div`
  width: 100%;
  height: 100%;
  overflow: auto;
`;

export const KVDetailValueText = styled.div`
  max-height: 100px;
  overflow-y: auto;
`;

export const KVDetailValueTD = styled.td`
  padding: 0.2em;
`;

export const KVDetailKeyTD = styled.td`
  padding: 0.2em;
  font-weight: bold;
  width: 120px;
`;

export const TraceDetailWrapper = styled.div`
  width: 100%;
  height: 100%;
  border: 1px solid #ddd;
  border-radius: 0.2em;
  overflow-y: auto;
  padding: 6px;
`;

export const TraceTimelineElementWrapper = styled.div`
  width: 100%;
  flex: 0 0 auto;
`;

type SplitProps = {
  split: `vertical` | `horizontal`;
};

export const TraceWrapper = styled.div<SplitProps>`
  width: 100%;
  height: 100%;
  font-size: 14px;
  display: flex;
  flex-direction: ${p => (p.split === `vertical` ? `row` : `column`)};
  justify-content: space-between;
`;

export const TraceTimelineWrapper = styled.div`
  height: 100%;
  width: 100%;
  position: relative;
`;

export const TraceDetail = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
`;

export const TraceTimeline = styled.div`
  height: 100%;
  position: relative;
  overflow: auto;
`;

export const TraceTimelineScale = styled.div`
  height: 100%;
  position: relative;
`;

export const SpanDetailIOSectionHeaderTd = styled.td`
  font-weight: bold;
  border-bottom: 1px solid #eee;
  padding-top: 1em;
  padding-bottom: 0.2em;
`;

export const SpanDetailSectionHeaderTd = styled.td`
  font-weight: bold;
  border-bottom: 2px solid #eee;
  padding-top: 1em;
  padding-bottom: 0.2em;
`;

export const TipOverlay = styled.div<{visible: boolean}>`
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: ${globals.BLACK_TRANSPARENT_2};
  z-index: 10;
  display: flex;
  justify-content: center;
  align-items: center;
  color: ${globals.WHITE};
  font-size: 20px;
  pointer-events: none;

  transition: opacity 0.2s;
  opacity: ${p => (p.visible ? 1 : 0)};
`;
