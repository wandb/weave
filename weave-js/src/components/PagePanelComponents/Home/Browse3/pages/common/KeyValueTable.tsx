import {Box} from '@mui/material';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import _ from 'lodash';
import moment from 'moment';
import React, {useContext, useEffect, useState} from 'react';

import {parseRefMaybe, SmallRef} from '../../../Browse2/SmallRef';
import {isPrimitive} from './util';

const VALUE_SPACE = 4;
const ROW_HEIGHT = 26;
const PADDING_GAP = 16;
const MAX_HEIGHT_MULT = 5;

export const KeyValueTable: React.FC<{
  data: {[key: string]: any};
  headerTitle?: string;
}> = props => {
  return (
    <Box
      sx={{
        border: `1px solid ${MOON_250}`,
        borderRadius: '4px',
      }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          tableLayout: 'fixed',
        }}>
        {props.headerTitle && (
          <thead>
            <tr
              style={{
                borderBottom: `1px solid ${MOON_250}`,
                backgroundColor: '#FAFAFA',
              }}>
              <th colSpan={VALUE_SPACE + 1}>{props.headerTitle}</th>
            </tr>
          </thead>
        )}
        <tbody>
          <KeyValueRowForObject objValue={props.data} />
        </tbody>
      </table>
    </Box>
  );
};

const baseKeyStyle: React.CSSProperties = {
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',

  padding: '4px, 8px, 4px, 8px',

  fontWeight: 600,

  height: `${ROW_HEIGHT}px`,
};

const parentKeyStyle: React.CSSProperties = {
  ...baseKeyStyle,
  borderTop: `1px solid ${MOON_250}`,
  borderBottom: `1px solid ${MOON_250}`,
  backgroundColor: '#FAFAFA',
  color: '#979a9e',
  position: 'sticky',
  top: 0,
  zIndex: 1,
};

const leafKeyStyle: React.CSSProperties = {
  ...baseKeyStyle,
  textAlign: 'right',
  borderRight: `1px solid ${MOON_250}`,
  paddingRight: '8px',
  verticalAlign: 'top',
  backgroundColor: '#fff',
  borderBottom: `1px solid ${MOON_250}`,
};

const valueStyle: React.CSSProperties = {
  paddingLeft: '8px',
  verticalAlign: 'top',
  borderBottom: `1px solid ${MOON_250}`,
};

const KeyValueRow: React.FC<{
  rowKey: string;
  rowValue: any;
}> = props => {
  const depth = useContext(DepthContext);
  const [open, setOpen] = React.useState(false);
  const cellRef = React.useRef<HTMLTableCellElement>(null);
  const [canExpand, setCanExpand] = useState(false);

  useEffect(() => {
    if (
      cellRef.current &&
      cellRef.current.clientHeight >= ROW_HEIGHT * MAX_HEIGHT_MULT - 5
    ) {
      setCanExpand(true);
    }
  }, []);

  if (isPrimitive(props.rowValue)) {
    const valRef = _.isString(props.rowValue)
      ? parseRefMaybe(props.rowValue)
      : null;
    let useVal: any = props.rowValue;
    if (valRef) {
      useVal = <SmallRef objRef={valRef} />;
    } else if (_.isString(props.rowValue)) {
      //   useVal = <SimplePopoverText text={props.rowValue} />;
      useVal = (
        <Box
          sx={{
            // maxHeight: !open ? `${ROW_HEIGHT * MAX_HEIGHT_MULT}px` : '50vh',
            overflowY: 'auto',
            overflowX: 'hidden',
            width: '100%',
          }}>
          <pre
            style={{
              width: '100%',
              // See https://developer.mozilla.org/en-US/docs/Web/CSS/white-space
              // We want to break on spaces, but also on newlines and preserve them
              whiteSpace: 'break-spaces',
              fontSize: '16px',
              margin: '0',
              fontFamily: 'Source Sans Pro',
            }}>
            {useVal}
          </pre>
        </Box>
      );
    } else if (_.isBoolean(props.rowValue)) {
      useVal = (props.rowValue as boolean).toString();
    } else if (_.isDate(props.rowValue)) {
      useVal = moment(props.rowValue as Date).format('YYYY-MM-DD HH:mm:ss');
    }
    return (
      <tr>
        <td
          onClick={() => {
            if (open || canExpand) {
              setOpen(!open);
            }
          }}
          style={{
            ...leafKeyStyle,
            // cursor: open || canExpand ? 'pointer' : 'auto',
          }}>
          {props.rowKey}
        </td>
        <td style={valueStyle} colSpan={VALUE_SPACE} ref={cellRef}>
          {useVal}
        </td>
      </tr>
    );
  } else if (_.isArray(props.rowValue)) {
    return (
      <KeyValueRow
        rowKey={props.rowKey}
        rowValue={_.fromPairs(props.rowValue.map((v, i) => [i, v]))}
      />
    );
  } else {
    return (
      <>
        <tr>
          <td
            colSpan={VALUE_SPACE + 1}
            style={{
              ...parentKeyStyle,
              paddingLeft: `${depth * PADDING_GAP}px`,
              top: (depth - 1) * ROW_HEIGHT,
            }}>
            {props.rowKey}
          </td>
        </tr>
        <KeyValueRowForObject objValue={props.rowValue} />
      </>
    );
  }
};

const DepthContext = React.createContext(0);

const KeyValueRowForObject: React.FC<{
  objValue: {[key: string]: any};
}> = props => {
  const depth = useContext(DepthContext);
  return (
    <DepthContext.Provider value={depth + 1}>
      {Object.entries(props.objValue).map(([key, value]) => {
        return <KeyValueRow key={key} rowKey={key} rowValue={value} />;
      })}
    </DepthContext.Provider>
  );
};
