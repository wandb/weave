import {
  MOON_100,
  MOON_250,
  MOON_350,
} from '@wandb/weave/common/css/color.styles';
import {constString, opGet} from '@wandb/weave/core';
import {useMakeMutation} from '@wandb/weave/react';
import _ from 'lodash';
import React, {Dispatch, SetStateAction, useMemo, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {Divider, Dropdown, Input, Popup} from 'semantic-ui-react';
import styled from 'styled-components';

import {IconOverflowHorizontal, IconWeaveLogoGray} from '../../Panel2/Icons';
import {WeaveAnimatedLoader} from '../../Panel2/WeaveAnimatedLoader';
import {DeleteActionModal} from '../DeleteActionModal';
import {SetPreviewNodeType} from './common';
import * as LayoutElements from './LayoutElements';

const TableRow = styled.tr<{$highlighted?: boolean}>`
  background-color: ${props => (props.$highlighted ? '#f8f9fa' : '')};
`;
TableRow.displayName = 'S.TableRow';

const CenterTable = styled.table`
  width: 100%;
  border: none;
  border-collapse: collapse;

  td {
    padding: 0px 15px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  td:first-child {
    padding-left: 12px;
  }

  tr {
    border-bottom: 1px solid ${MOON_250};
    color: #2b3038;
  }

  /* This whole bit is to keep borders with sticky! */
  thead {
    position: sticky;
    top: 0;

    tr {
      border-top: none;
      border-bottom: none;
    }
    &:after,
    &:before {
      content: '';
      position: absolute;
      left: 0;
      width: 100%;
    }
    &:after {
      bottom: 0;
      border-bottom: 1px solid ${MOON_250};
    }
  }
  /*End sticky with border fix  */

  thead {
    tr {
      text-transform: uppercase;
      height: 48px;
      background-color: #f5f6f7;
      color: #8e949e;
      font-size: 14px;
      font-weight: 600;
    }
  }
  tbody {
    font-size: 16px;
    tr {
      height: 64px;

      &:hover {
        cursor: pointer;
        background-color: #f8f9fa;
      }
    }
    tr > td:first-child {
      font-weight: 600;
    }
  }
`;
CenterTable.displayName = 'S.CenterTable';

const CenterTableActionCellAction = styled(LayoutElements.HBlock)<{
  isDisabled?: boolean;
}>`
  padding: 0px 12px;
  border-radius: 4px;
  height: 36px;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  cursor: ${props => (props.isDisabled ? 'default' : 'pointer')};
  color: ${props => (props.isDisabled ? MOON_350 : 'inherit')};
  &:hover {
    background-color: ${props => (props.isDisabled ? 'inherit' : MOON_100)};
  }
`;
CenterTableActionCellAction.displayName = 'S.CenterTableActionCellAction';

const CenterTableActionCellContents = styled(LayoutElements.VStack)`
  align-items: center;
  justify-content: center;
`;
CenterTableActionCellContents.displayName = 'S.CenterTableActionCellContents';

const CenterTableActionCellIcon = styled(LayoutElements.VStack)`
  align-items: center;
  justify-content: center;
  height: 32px;
  width: 32px;
  border-radius: 4px;
  &:hover {
    background-color: #a9edf252;
    color: #038194;
  }
`;
CenterTableActionCellIcon.displayName = 'S.CenterTableActionCellIcon';

const CenterSpaceTableSpace = styled(LayoutElements.Space)`
  overflow: auto;
`;
CenterSpaceTableSpace.displayName = 'S.CenterSpaceTableSpace';

const CenterSpaceControls = styled(LayoutElements.HBlock)`
  gap: 8px;
`;
CenterSpaceControls.displayName = 'S.CenterSpaceControls';

const CenterSpaceTitle = styled(LayoutElements.HBlock)`
  font-size: 24px;
  font-weight: 600;
  padding: 12px 8px;
`;
CenterSpaceTitle.displayName = 'S.CenterSpaceTitle';

const CenterSpaceHeader = styled(LayoutElements.VBlock)`
  padding: 12px 16px;
  gap: 12px;
  border-bottom: 1px solid ${MOON_250};
`;
CenterSpaceHeader.displayName = 'S.CenterSpaceHeader';

export type CenterBrowserDataType<
  E extends {[key: string]: string | number} = {}
> = {
  _id: string;
} & E;

export type CenterBrowserActionSingularType<RT extends CenterBrowserDataType> =
  {
    icon: React.FC;
    label: string;
    onClick: (row: RT, index: number) => void;
    disabled?: (row: RT) => boolean;
  };

export type CenterBrowserActionType<RT extends CenterBrowserDataType> = Array<
  CenterBrowserActionSingularType<RT>
>;

type CenterBrowserProps<RT extends CenterBrowserDataType> = {
  title: string;
  data: RT[];
  selectedRowId?: string;
  setSelectedRowId?: Dispatch<SetStateAction<string | undefined>>;
  setPreviewNode?: SetPreviewNodeType;

  noDataCTA?: string;
  breadcrumbs?: Array<{
    key: string;
    text: string;
    onClick?: () => void;
  }>;
  loading?: boolean;
  columns?: string[];
  actions?: Array<CenterBrowserActionType<RT>>;
  allowSearch?: boolean;
  filters?: {
    [key: string]: {
      placeholder: string;
    };
  };

  // id of an artifact that is pending deletion
  deletingId?: string;
  setDeletingId?: Dispatch<SetStateAction<string | undefined>>;

  isModalActing?: boolean;
  setIsModalActing?: Dispatch<SetStateAction<boolean>>;
  deleteTypeString?: string;
};

export const CenterBrowser = <RT extends CenterBrowserDataType>(
  props: CenterBrowserProps<RT>
) => {
  const history = useHistory();
  const [searchText, setSearchText] = useState('');
  const [filters, setFilters] = useState<{
    [key: string]: string | null | undefined;
  }>({});

  const filteredData = useMemo(() => {
    if (props.loading) {
      return [];
    }
    const canApplySearch =
      props.allowSearch || searchText === '' || searchText == null;
    const canApplyFilters = Object.values(filters).filter(
      v => v != null && v !== ''
    );
    if (!canApplySearch && !canApplyFilters) {
      return props.data;
    }
    return props.data.filter(d => {
      const passesSearch =
        !canApplySearch ||
        Object.values(d).some(v => {
          return (v ?? '')
            .toString()
            .toLowerCase()
            .includes(searchText.toLowerCase());
        });
      const passesFilters =
        !canApplyFilters ||
        _.every(
          Object.entries(filters).map(([k, v], i) => {
            return v == null || v === '' || (k in d && (d as any)[k] === v);
          })
        );
      return passesSearch && passesFilters;
    });
  }, [filters, props.allowSearch, props.data, props.loading, searchText]);

  const filterSpec = useMemo(() => {
    return Object.entries(props.filters ?? {}).map(([k, v], i) => {
      const options = _.uniq(props.data.map(d => (d as any)[k]));
      return {
        placeholder: v.placeholder,
        options: options.map(o => {
          return {key: o, text: o, value: o};
        }),
        onChange: (val: string) => {
          setFilters(f => {
            const copy = {...f};
            copy[k] = val;
            return copy;
          });
        },
      };
    });
  }, [props.data, props.filters]);

  const showControls =
    props.allowSearch || Object.keys(props.filters ?? {}).length > 0;
  const allActions = (props.actions ?? []).flatMap(a => a);
  const primaryAction = allActions.length > 0 ? allActions[0] : undefined;
  const columns = useMemo(() => {
    if (props.columns != null) {
      return props.columns;
    }
    return Object.keys(props.data[0] ?? {}).filter(k => !k.startsWith('_'));
  }, [props.columns, props.data]);
  const hasOverflowActions = allActions.length > 1;

  const makeMutation = useMakeMutation();

  return (
    <>
      <DeleteActionModal
        open={props.deletingId != null}
        onClose={() => props.setDeletingId?.(undefined)}
        acting={props.isModalActing ?? false}
        onDelete={async () => {
          props.setIsModalActing?.(true);
          const artifactNode = opGet({
            uri: constString(props.deletingId!),
          });
          await makeMutation(artifactNode, 'delete_artifact', {});
          props.setDeletingId?.(undefined);
          props.setIsModalActing?.(false);
          // If the user is deleting the selected row, navigate up a level
          if (
            props.deletingId?.endsWith(`/${props.selectedRowId}:latest/obj`)
          ) {
            history.push('.');
          }
        }}
        deleteTypeString={props.deleteTypeString}
      />

      <CenterSpaceHeader>
        <CenterSpaceTitle>
          <span
            style={{
              color: '#8E949E',
            }}>
            {(props.breadcrumbs ?? []).map((comp, ndx) => {
              const style: React.CSSProperties = {};
              if (comp.onClick) {
                style.cursor = 'pointer';
              }
              return (
                <React.Fragment key={comp.key}>
                  <span style={style} onClick={comp.onClick}>
                    {comp.text}
                  </span>
                  <span
                    style={{
                      margin: '0px 10px',
                    }}>
                    /
                  </span>
                </React.Fragment>
              );
            })}
          </span>
          {props.title}
        </CenterSpaceTitle>
        {showControls && (
          <CenterSpaceControls>
            {props.allowSearch && (
              <Input
                style={{
                  width: '100%',
                }}
                icon="search"
                iconPosition="left"
                placeholder="Search"
                onChange={e => {
                  setSearchText(e.target.value);
                }}
              />
            )}
            {filterSpec.map((filter, i) => (
              <Dropdown
                key={i}
                style={{
                  boxShadow: 'none',
                }}
                selection
                clearable
                placeholder={filter.placeholder}
                options={filter.options}
                onChange={(e, data) => {
                  filter.onChange(data.value as string);
                }}
              />
            ))}
          </CenterSpaceControls>
        )}
      </CenterSpaceHeader>
      <CenterSpaceTableSpace>
        <CenterTable>
          <thead>
            <tr>
              {columns.map(c => (
                <td key={c}>{c}</td>
              ))}
              {hasOverflowActions && (
                <td
                  style={{
                    width: '64px',
                  }}></td>
              )}
            </tr>
          </thead>
          <tbody>
            {filteredData.map((row, i) => (
              <TableRow
                key={row._id}
                onClick={() => primaryAction?.onClick(row, i)}
                $highlighted={props.selectedRowId === row._id}>
                {columns.map(c => (
                  <td key={c}>{(row as any)[c]}</td>
                ))}
                {hasOverflowActions && (
                  <td>
                    <ActionCell row={row} actions={props.actions} />
                  </td>
                )}
              </TableRow>
            ))}
          </tbody>
        </CenterTable>
        {(props.data.length === 0 || props.loading) && (
          <LayoutElements.VStack
            style={{
              alignItems: 'center',
              justifyContent: 'center',
              gap: '16px',
              color: '#8e949e',
            }}>
            {props.loading ? (
              <WeaveAnimatedLoader style={{height: '64px', width: '64px'}} />
            ) : (
              <IconWeaveLogoGray
                style={{
                  height: '64px',
                  width: '64px',
                }}
              />
            )}
            <div>{props.loading ? '' : props.noDataCTA}</div>
          </LayoutElements.VStack>
        )}
      </CenterSpaceTableSpace>
    </>
  );
};

export const ActionCell = <RT extends CenterBrowserDataType>(props: {
  row: RT;
  actions?: Array<CenterBrowserActionType<RT>>;
}) => {
  const [popupOpen, setPopupOpen] = useState(false);
  return (
    <CenterTableActionCellContents>
      <Popup
        onClose={() => setPopupOpen(false)}
        onOpen={() => setPopupOpen(true)}
        open={popupOpen}
        style={{
          padding: '6px 6px',
        }}
        content={
          <LayoutElements.VStack
            onClick={e => {
              e.stopPropagation();
            }}>
            {props.actions?.flatMap((action, j) => {
              const actions = action.map((a, k) => (
                <CenterTableActionCellAction
                  key={'' + j + '_' + k}
                  onClick={e => {
                    if (a.disabled != null && a.disabled(props.row)) {
                      return;
                    }
                    setPopupOpen(false);
                    e.stopPropagation();
                    a.onClick(props.row, j);
                  }}
                  isDisabled={a.disabled != null && a.disabled(props.row)}>
                  <a.icon />
                  {a.label}
                </CenterTableActionCellAction>
              ));
              if (j < props.actions!.length - 1) {
                actions.push(
                  <Divider key={'d' + j} style={{margin: '6px 0px'}} />
                );
              }
              return actions;
            })}
          </LayoutElements.VStack>
        }
        basic
        on="click"
        trigger={
          <CenterTableActionCellIcon
            onClick={e => {
              e.stopPropagation();
            }}>
            <IconOverflowHorizontal />
          </CenterTableActionCellIcon>
        }
      />
    </CenterTableActionCellContents>
  );
};
