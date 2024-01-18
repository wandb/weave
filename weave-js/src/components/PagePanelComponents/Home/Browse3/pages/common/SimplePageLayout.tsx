import MoreVertIcon from '@mui/icons-material/MoreVert';
import {Box, ListItemText, MenuList, Popover, Tab, Tabs} from '@mui/material';
// import {Menu} from '@mui/base/Menu';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import React, {createContext, useContext, useMemo} from 'react';

import {ErrorBoundary} from '../../../../../ErrorBoundary';
import _ from 'lodash';
import {SmallRef, parseRefMaybe} from '../../../Browse2/SmallRef';

type SimplePageLayoutContextType = {
  headerPrefix?: React.ReactNode;
};

export const SimplePageLayoutContext =
  createContext<SimplePageLayoutContextType>({});

export const SimplePageLayout: React.FC<{
  title: string;
  tabs: Array<{
    label: string;
    content: React.ReactNode;
  }>;
  menuItems?: Array<{
    label: string;
    onClick: () => void;
  }>;
  leftSidebar?: React.ReactNode;
  headerContent?: React.ReactNode;
}> = props => {
  const simplePageLayoutContextValue = useContext(SimplePageLayoutContext);
  const [tabId, setTabId] = React.useState(0);
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabId(newValue);
  };
  const tabContent = useMemo(
    () => props.tabs[tabId].content,
    [props.tabs, tabId]
  );
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
        height: '100%',
      }}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          backgroundColor: 'white',
          pb: 0,
          // pl: 2,
          // pr: 2,
          height: props.headerContent ? undefined : 65, // manual to match sidebar
          maxHeight: props.headerContent ? '50%' : undefined,

          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          flexDirection: props.headerContent ? 'column' : 'row',
          alignItems: props.headerContent ? 'flex-start' : 'flex-end',
          justifyContent: props.headerContent ? 'flex-start' : 'space-between',
          flex: '0 0 auto',
        }}>
        <Box
          sx={{
            height: 65, // manual to match sidebar
            flex: '0 0 65px',
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'flex-end',
            gap: 1,
            pl: 2,
            pr: 2,
          }}>
          {simplePageLayoutContextValue.headerPrefix}
          <Box
            sx={{
              pb: 2,
              fontWeight: 600,
              fontSize: '1.5rem',
              flex: '1 1 auto',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
            {props.title}
          </Box>
          <Box
            sx={{
              flex: '0 0 auto',
            }}>
            {props.menuItems && <ActionMenu menuItems={props.menuItems} />}
          </Box>
        </Box>
        {props.headerContent && (
          <Box
            sx={{
              width: '100%',
              overflow: 'auto',
              borderTop: '1px solid #e0e0e0',
              borderBottom: '1px solid #e0e0e0',
              // pt: 1,
              // pb: 1,
            }}>
            {props.headerContent}
          </Box>
        )}
        <Tabs
          variant="scrollable"
          scrollButtons="auto"
          value={tabId}
          onChange={handleTabChange}>
          {props.tabs.map((tab, i) => (
            <Tab key={i} label={tab.label} />
          ))}
        </Tabs>
      </Box>
      <Box
        sx={{
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'row',
          flex: '1 1 auto',
        }}>
        {props.leftSidebar && (
          <Box
            sx={{
              width: '30%',
              flex: '0 0 30%',
              overflow: 'hidden',
              height: '100%',
              maxHeight: '100%',
              borderRight: '1px solid #e0e0e0',
            }}>
            {props.leftSidebar}
          </Box>
        )}
        <Box
          component="main"
          sx={{
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            flex: '1 1 auto',
          }}>
          <ErrorBoundary key={tabId}>{tabContent}</ErrorBoundary>
        </Box>
      </Box>
    </Box>
  );
};

const ActionMenu: React.FC<{
  menuItems: Array<{
    label: string;
    onClick: () => void;
  }>;
}> = props => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <Box
      sx={{
        height: '47px',
      }}>
      <IconButton
        aria-label="more"
        id="long-button"
        aria-controls={open ? 'long-menu' : undefined}
        aria-expanded={open ? 'true' : undefined}
        aria-haspopup="true"
        onClick={handleClick}>
        <MoreVertIcon />
      </IconButton>
      <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
        <Box sx={{width: 320, maxWidth: '100%'}}>
          <MenuList>
            {props.menuItems.map((item, i) => (
              <MenuItem
                key={i}
                onClick={() => {
                  handleClose();
                  item.onClick();
                }}>
                <ListItemText>{item.label}</ListItemText>
              </MenuItem>
            ))}
          </MenuList>
        </Box>
      </Menu>
    </Box>
  );
};

export const ScrollableTabContent: React.FC<{
  sx?: React.CSSProperties;
}> = props => {
  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        flexGrow: 1,
        overflow: 'auto',
        p: 2,
        ...(props.sx ?? {}),
      }}>
      {props.children}
    </Box>
  );
};

const isPrimitive = (val: any) => {
  return (
    React.isValidElement(val) ||
    _.isString(val) ||
    _.isNumber(val) ||
    _.isBoolean(val) ||
    _.isDate(val) ||
    _.isNil(val)
  );
};

const flattenObject = (val: any): any => {
  if (isPrimitive(val)) {
    return val;
  } else if (_.isArray(val)) {
    return flattenObject(_.fromPairs(val.map((v, i) => [i, v])));
  } else {
    return _.fromPairs(
      Object.entries(val).flatMap(([key, val]) => {
        if (isPrimitive(val)) {
          return [[key, val]];
        }
        return Object.entries(flattenObject(val)).map(([subKey, subVal]) => {
          return [key + '.' + subKey, subVal];
        });
      })
    );
  }
};

const keyStyle: React.CSSProperties = {
  // fontWeight: 600,
  // marginRight: 10,
  // paddingRight: 10,

  // align text to the top
  // display: 'flex',
  flexDirection: 'column',
  justifyContent: 'flex-start',

  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',

  backgroundColor: '#FAFAFA',
  color: '#979a9e',

  padding: '8px',

  borderTop: '1px solid rgba(224, 224, 224, 1)',
  borderBottom: '1px solid rgba(224, 224, 224, 1)',
};

export const SimpleKeyValueTable: React.FC<{
  data: {[key: string]: any};
}> = props => {
  const flattenedData = useMemo(() => flattenObject(props.data), [props.data]);
  const numCols = useMemo(
    () =>
      Math.max(
        ...Object.keys(flattenedData).map(key => key.split('.').length)
      ) + 1,
    [flattenedData]
  );
  let lastKeyParts: string[] = [];
  const headerWidth = 50 / (numCols - 1);
  return (
    <table
      style={{
        borderRadius: '4px',
        maxWidth: '100%',
        borderCollapse: 'collapse',
        tableLayout: 'fixed',
        width: '100%',
        overflow: 'hidden',
      }}>
      <thead>
        {/* Width setters */}
        <tr>
          {_.range(numCols - 1).map(kpi => {
            return (
              <td
                key={kpi}
                style={{
                  width: `${headerWidth}%`,
                  height: '0px',
                  overflow: 'hidden',
                  padding: '0px',
                }}
              />
            );
          })}
          <td
            style={{
              width: `50%`,
              height: '0px',
              overflow: 'hidden',
              padding: '0px',
            }}
          />
        </tr>
      </thead>
      <tbody>
        {Object.entries(flattenedData).map(([key, val], ndx) => {
          const keyParts = key.split('.');
          const valCols = numCols - keyParts.length;
          const valRef = _.isString(val) ? parseRefMaybe(val) : null;
          const isFirst = ndx === 0;
          const isLast = ndx === Object.keys(flattenedData).length - 1;

          // Find common prefix of current key and last key
          let i = 0;
          while (i < keyParts.length && i < lastKeyParts.length) {
            if (keyParts[i] !== lastKeyParts[i]) {
              break;
            }
            i++;
          }
          lastKeyParts = keyParts;

          const newKeyParts = keyParts.slice(i);

          return (
            <>
              <tr key={key}>
                {/* {_.range(i).map(kpi => {
                  return (
                    <td
                      key={kpi}
                      style={{
                        ...keyStyle,
                        borderTop: 'none',
                        borderBottom: 'none',
                      }}
                    />
                  );
                })} */}
                {newKeyParts.map((part, kpi) => {
                  const prefix = keyParts.slice(0, i + kpi + 1).join('.') + '.';
                  const rowSpan = Math.max(
                    1,
                    Object.keys(flattenedData).filter(k => k.startsWith(prefix))
                      .length
                  );
                  // console.log('rowSpan', key, part, prefix, rowSpan);
                  return (
                    <td
                      key={i}
                      style={{
                        ...keyStyle,
                        ...(isFirst ? {borderTop: 'none'} : {}),
                        ...(isLast ? {borderBottom: 'none'} : {}),
                      }}
                      rowSpan={rowSpan}>
                      {part}
                    </td>
                  );
                })}
                <td
                  colSpan={valCols}
                  style={{
                    // width: '0.1%',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    padding: '8px',
                  }}>
                  {valRef ? (
                    <SmallRef objRef={valRef} />
                  ) : _.isString(val) ? (
                    <SimplePopoverText text={val as string} />
                  ) : (
                    val
                  )}
                </td>
              </tr>
              {/* {key.endsWith('content') && (
                <tr>
                  <td colSpan={numCols}>
                    <Box
                      sx={{
                        width: '100%',
                        borderTop: '1px solid rgba(224, 224, 224, 1)',
                        borderBottom: '1px solid rgba(224, 224, 224, 1)',
                      }}>
                      {val}
                    </Box>
                  </td>
                </tr>
              )} */}
            </>
          );
        })}
      </tbody>
    </table>
  );
};

const SimplePopoverText: React.FC<{
  text: string;
}> = props => {
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);

  const handlePopoverOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handlePopoverClose = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  return (
    <>
      <Box
        aria-owns={open ? 'mouse-over-popover' : undefined}
        aria-haspopup="true"
        onMouseEnter={handlePopoverOpen}
        onMouseLeave={handlePopoverClose}
        sx={{
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          maxWidth: '100%',
        }}>
        {props.text}
      </Box>
      <Popover
        id="mouse-over-popover"
        sx={{
          pointerEvents: 'none',
        }}
        PaperProps={{
          style: {maxWidth: '50%'},
        }}
        open={open}
        anchorEl={anchorEl}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        onClose={handlePopoverClose}
        disableRestoreFocus>
        {props.text}
      </Popover>
    </>
  );
};
