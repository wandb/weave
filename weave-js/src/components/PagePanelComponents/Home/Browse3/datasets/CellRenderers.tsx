import {Box, Tooltip, Typography} from '@mui/material';
import {
  GridRenderCellParams,
  GridRenderEditCellParams,
} from '@mui/x-data-grid-pro';
import {MOON_600} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {UserLink} from '@wandb/weave/components/UserLink';
import set from 'lodash/set';
import React, {useCallback, useState} from 'react';

import {CellValue} from '../../Browse2/CellValue';
import {isRefPrefixedString} from '../filters/common';
import {DatasetRow, useDatasetEditContext} from './DatasetEditorContext';
import {CodeEditor} from './editors/CodeEditor';
import {DiffEditor} from './editors/DiffEditor';
import {TextEditor} from './editors/TextEditor';
import {EditorMode, EditPopover} from './EditPopover';

export const CELL_COLORS = {
  DELETED: '#FFE6E6', // Red 200
  EDITED: '#E0EDFE', // Blue 200
  NEW: '#E4F7EE', // Green 200
  TRANSPARENT: 'transparent',
} as const;

export const DELETED_CELL_STYLES = {
  opacity: 0.5,
  textDecoration: 'line-through' as const,
} as const;

const cellViewingStyles = {
  height: '100%',
  width: '100%',
  display: 'flex',
  padding: '8px 12px',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'background-color 0.2s ease',
};

interface CellViewingRendererProps {
  isEdited?: boolean;
  isDeleted?: boolean;
  isNew?: boolean;
  isEditing?: boolean;
  serverValue?: any;
  disableNewRowHighlight?: boolean;
}

interface FeedbackItem {
  id: string;
  feedback_type: string;
  created_at: string;
  creator: string | null;
  wb_user_id: string;
  payload: Record<string, any>;
}

export const FeedbackCellRenderer: React.FC<{
  value: FeedbackItem[] | any;
}> = ({value}) => {
  // Convert different feedback formats to a consistent format for display
  const normalizeFeedback = (feedbackData: any): FeedbackItem[] => {
    if (!feedbackData) return [];

    // If it's a plain object with feedback items as keys (the most common W&B format)
    if (typeof feedbackData === 'object' && !Array.isArray(feedbackData)) {
      // Check each key to see if it contains feedback (wandb.reaction, wandb.note, etc.)
      const feedbackItems: FeedbackItem[] = [];

      Object.entries(feedbackData).forEach(([key, value]) => {
        // If the value is an object and has a feedback_type field, it's likely a feedback item
        if (typeof value === 'object' && value && 'feedback_type' in value) {
          feedbackItems.push(value as FeedbackItem);
        }
        // Handle the keys like wandb.reaction.1, wandb.note.1
        else if (key.match(/^wandb\.(reaction|note)\.\d+$/)) {
          // For these keys, create a FeedbackItem with the full original key as the feedback_type
          feedbackItems.push({
            id: key,
            feedback_type: key, // Use the full key as the feedback_type to preserve numbering
            created_at: new Date().toISOString(),
            creator: null,
            wb_user_id: '',
            payload: value as Record<string, any>,
          });
        }
      });

      return feedbackItems;
    }

    // Handle array of feedback items (less common)
    if (Array.isArray(feedbackData) && feedbackData.length > 0) {
      return feedbackData;
    }

    return [];
  };

  const normalizedFeedback = normalizeFeedback(value);

  if (!normalizedFeedback.length) {
    return <Box sx={{p: '4px 8px', color: 'text.secondary'}}>No feedback</Box>;
  }

  // Count different types of feedback
  const counts: Record<string, number> = {
    reaction: 0,
    note: 0,
    other: 0,
  };

  normalizedFeedback.forEach(item => {
    if (
      item.feedback_type === 'wandb.reaction' ||
      item.feedback_type.startsWith('wandb.reaction.')
    ) {
      counts.reaction += 1;
    } else if (
      item.feedback_type === 'wandb.note' ||
      item.feedback_type.startsWith('wandb.note.')
    ) {
      counts.note += 1;
    } else {
      counts.other += 1;
    }
  });

  // Group feedback by type for better organization in tooltip
  const reactions = normalizedFeedback.filter(
    item =>
      item.feedback_type === 'wandb.reaction' ||
      item.feedback_type.startsWith('wandb.reaction.')
  );
  const notes = normalizedFeedback.filter(
    item =>
      item.feedback_type === 'wandb.note' ||
      item.feedback_type.startsWith('wandb.note.')
  );
  const others = normalizedFeedback.filter(
    item =>
      !(
        item.feedback_type === 'wandb.reaction' ||
        item.feedback_type.startsWith('wandb.reaction.')
      ) &&
      !(
        item.feedback_type === 'wandb.note' ||
        item.feedback_type.startsWith('wandb.note.')
      )
  );

  // Generate tooltip content
  const tooltipContent = (
    <Box
      sx={{
        p: 1,
        minWidth: 300,
        maxHeight: 400,
        overflow: 'auto',
      }}>
      {reactions.length > 0 && (
        <Box sx={{mb: 2}}>
          <Typography variant="subtitle2" sx={{fontWeight: 600, mb: 1}}>
            Reactions ({reactions.length})
          </Typography>
          {reactions.map((item, index) => (
            <Box
              key={`reaction-${item.id || index}`}
              sx={{
                mb: 1,
                p: 1,
                borderRadius: 1,
                bgcolor: 'rgba(0, 0, 0, 0.03)',
                '&:last-child': {mb: 0},
              }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  mb: 0.5,
                }}>
                <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                  {item.wb_user_id && (
                    <UserLink userId={item.wb_user_id} includeName />
                  )}
                </Box>
                <Typography
                  variant="caption"
                  sx={{color: 'text.secondary', flexShrink: 0}}>
                  {new Date(item.created_at).toLocaleString()}
                </Typography>
              </Box>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  bgcolor: 'background.paper',
                  p: 1,
                  borderRadius: 1,
                  border: '1px solid',
                  borderColor: 'divider',
                }}>
                <Typography variant="body2">
                  {item.payload.emoji || item.payload.alias || 'Reaction'}
                </Typography>
              </Box>
            </Box>
          ))}
        </Box>
      )}

      {notes.length > 0 && (
        <Box sx={{mb: 2}}>
          <Typography variant="subtitle2" sx={{fontWeight: 600, mb: 1}}>
            Notes ({notes.length})
          </Typography>
          {notes.map((item, index) => (
            <Box
              key={`note-${item.id || index}`}
              sx={{
                mb: 1,
                p: 1,
                borderRadius: 1,
                bgcolor: 'rgba(0, 0, 0, 0.03)',
                '&:last-child': {mb: 0},
              }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  mb: 0.5,
                }}>
                <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                  {item.wb_user_id && (
                    <UserLink userId={item.wb_user_id} includeName />
                  )}
                </Box>
                <Typography
                  variant="caption"
                  sx={{color: 'text.secondary', flexShrink: 0}}>
                  {new Date(item.created_at).toLocaleString()}
                </Typography>
              </Box>
              <Typography
                variant="body2"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  bgcolor: 'background.paper',
                  p: 1,
                  borderRadius: 1,
                  border: '1px solid',
                  borderColor: 'divider',
                }}>
                {item.payload.note || JSON.stringify(item.payload, null, 2)}
              </Typography>
            </Box>
          ))}
        </Box>
      )}

      {others.length > 0 && (
        <Box>
          <Typography variant="subtitle2" sx={{fontWeight: 600, mb: 1}}>
            Other Feedback ({others.length})
          </Typography>
          {others.map((item, index) => (
            <Box
              key={`other-${item.id || index}`}
              sx={{
                mb: 1,
                p: 1,
                borderRadius: 1,
                bgcolor: 'rgba(0, 0, 0, 0.03)',
                '&:last-child': {mb: 0},
              }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  mb: 0.5,
                }}>
                <Box sx={{display: 'flex', alignItems: 'center', gap: 0.5}}>
                  <Typography variant="subtitle2" sx={{fontWeight: 600}}>
                    {item.feedback_type}
                  </Typography>
                  {item.wb_user_id && (
                    <Typography
                      variant="caption"
                      sx={{color: 'text.secondary', ml: 1}}>
                      · <UserLink userId={item.wb_user_id} includeName />
                    </Typography>
                  )}
                </Box>
                {item.creator && (
                  <Typography
                    variant="caption"
                    sx={{color: 'text.secondary', flexShrink: 0}}>
                    {new Date(item.created_at).toLocaleString()}
                  </Typography>
                )}
              </Box>
              <Typography
                variant="body2"
                sx={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}>
                {typeof item.payload === 'string'
                  ? item.payload
                  : JSON.stringify(item.payload, null, 2)}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );

  // Create compact display
  const summary = (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        height: '100%',
        pl: 1,
        flexWrap: 'nowrap',
      }}>
      {normalizedFeedback.length === 0 ? (
        <Typography variant="caption" sx={{color: 'text.secondary'}}>
          No feedback
        </Typography>
      ) : (
        <>
          <Typography
            variant="body2"
            sx={{
              fontWeight: 600,
              ml: 1,
              color: MOON_600,
              fontFamily: '"Source Sans Pro"',
            }}>
            Feedback
          </Typography>

          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              flexWrap: 'nowrap',
            }}>
            {counts.reaction > 0 && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  bgcolor: 'rgba(0, 0, 0, 0.05)',
                  borderRadius: '4px',
                  px: 0.5,
                  py: 0.25,
                }}>
                <Icon name="add-reaction" width={12} height={12} />
                <Typography variant="caption" sx={{ml: 0.5, fontWeight: 600}}>
                  {counts.reaction}
                </Typography>
              </Box>
            )}

            {counts.note > 0 && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  bgcolor: 'rgba(0, 0, 0, 0.05)',
                  borderRadius: '4px',
                  px: 0.5,
                  py: 0.25,
                }}>
                <Icon name="forum-chat-bubble" width={12} height={12} />
                <Typography variant="caption" sx={{ml: 0.5, fontWeight: 600}}>
                  {counts.note}
                </Typography>
              </Box>
            )}

            {counts.other > 0 && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  bgcolor: 'rgba(0, 0, 0, 0.05)',
                  borderRadius: '4px',
                  px: 0.5,
                  py: 0.25,
                }}>
                <Typography variant="caption" sx={{fontWeight: 600}}>
                  +{counts.other}
                </Typography>
              </Box>
            )}
          </Box>
        </>
      )}
    </Box>
  );

  return (
    <Tooltip
      title={tooltipContent}
      placement="right-start"
      arrow
      enterDelay={300}
      leaveDelay={300}
      PopperProps={{
        popperOptions: {
          modifiers: [
            {
              name: 'preventOverflow',
              options: {
                boundary: window,
                altAxis: true,
                padding: 16,
              },
            },
            {
              name: 'flip',
              options: {
                altBoundary: true,
                fallbackPlacements: ['left-start', 'bottom', 'top'],
              },
            },
          ],
        },
        sx: {
          '& .MuiTooltip-tooltip': {
            bgcolor: 'background.paper',
            color: 'text.primary',
            boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.1)',
            border: '1px solid',
            borderColor: 'divider',
            p: 0,
            maxHeight: '80vh', // Limit height to 80% of viewport
            overflowY: 'auto',
          },
        },
      }}>
      {summary}
    </Tooltip>
  );
};

export const CellViewingRenderer: React.FC<
  GridRenderCellParams & CellViewingRendererProps
> = ({
  value,
  isEdited = false,
  isDeleted = false,
  isNew = false,
  isEditing = false,
  api,
  id,
  field,
  serverValue,
  disableNewRowHighlight = false,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const {setEditedRows, setAddedRows, setFieldEdited} = useDatasetEditContext();

  // Special handling for feedback field
  const isFeedbackField =
    field === 'summary.weave.feedback' ||
    (typeof value === 'object' &&
      value !== null &&
      Object.keys(value).some(key =>
        key.match(/^wandb\.(reaction|note)\.\d+$/)
      ));

  if (isFeedbackField) {
    const backgroundColor = isDeleted
      ? CELL_COLORS.DELETED
      : isEdited
      ? CELL_COLORS.EDITED
      : isNew && !disableNewRowHighlight
      ? CELL_COLORS.NEW
      : CELL_COLORS.TRANSPARENT;

    return (
      <Box
        sx={{
          height: '100%',
          backgroundColor,
          opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
          textDecoration: isDeleted
            ? DELETED_CELL_STYLES.textDecoration
            : 'none',
        }}>
        <FeedbackCellRenderer value={value} />
      </Box>
    );
  }

  const isWeaveUrl = isRefPrefixedString(value);
  const isEditable =
    !isWeaveUrl && typeof value !== 'object' && typeof value !== 'boolean';

  const handleEditClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (isEditable) {
      api.startCellEditMode({id, field});
    }
  };

  const handleRevert = (event: React.MouseEvent) => {
    event.stopPropagation();
    const existingRow = api.getRow(id);
    const updatedRow = {...existingRow};

    set(updatedRow, field, serverValue);
    api.updateRows([{id, ...updatedRow}]);
    api.setEditCellValue({id, field, value: serverValue});
    setEditedRows(prev => {
      const newMap = new Map(prev);
      newMap.set(existingRow.___weave?.index, updatedRow);
      return newMap;
    });
    if (existingRow.___weave?.index !== undefined) {
      setFieldEdited(existingRow.___weave.index, field, false);
    }
  };

  const getBackgroundColor = () => {
    if (isDeleted) {
      return CELL_COLORS.DELETED;
    }
    if (isEdited) {
      return CELL_COLORS.EDITED;
    }
    if (isNew && !disableNewRowHighlight) {
      return CELL_COLORS.NEW;
    }
    return CELL_COLORS.TRANSPARENT;
  };

  if (typeof value === 'boolean') {
    const handleToggle = (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      const existingRow = api.getRow(id);
      const updatedRow = {...existingRow, [field]: !value};
      api.updateRows([{id, ...updatedRow}]);
      const rowToUpdate = {...updatedRow};

      if (existingRow.___weave?.isNew) {
        setAddedRows(prev => {
          const newMap = new Map(prev);
          newMap.set(existingRow.___weave?.id, rowToUpdate);
          return newMap;
        });
      } else {
        if (!rowToUpdate.___weave.editedFields) {
          rowToUpdate.___weave.editedFields = new Set<string>();
        }
        rowToUpdate.___weave.editedFields.add(field);
        setEditedRows(prev => {
          const newMap = new Map(prev);
          newMap.set(existingRow.___weave?.index, rowToUpdate);
          return newMap;
        });
      }
    };

    return (
      <Tooltip
        title="Click to toggle"
        enterDelay={1000}
        enterNextDelay={1000}
        leaveDelay={0}
        placement="top"
        slotProps={{
          tooltip: {
            sx: {
              fontFamily: '"Source Sans Pro", sans-serif',
              fontSize: '14px',
            },
          },
        }}>
        <Box
          onClick={handleToggle}
          onDoubleClick={handleToggle}
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            width: '100%',
            backgroundColor: getBackgroundColor(),
            opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
            textDecoration: isDeleted
              ? DELETED_CELL_STYLES.textDecoration
              : 'none',
            cursor: 'pointer',
            transition: 'background-color 0.2s ease',
            borderLeft: '1px solid transparent',
            borderRight: '1px solid transparent',
            '&:hover': {
              borderLeft: '1px solid #DFE0E2',
              borderRight: '1px solid #DFE0E2',
            },
          }}>
          <Icon
            name={value ? 'checkmark' : 'close'}
            height={20}
            width={20}
            style={{
              color: value ? '#00875A' : '#CC2944',
            }}
          />
        </Box>
      </Tooltip>
    );
  }

  if (!isEditable) {
    return (
      <Tooltip
        title="Cell type cannot be edited"
        enterDelay={1000}
        enterNextDelay={1000}
        leaveDelay={0}
        placement="top"
        slotProps={{
          tooltip: {
            sx: {
              fontFamily: '"Source Sans Pro", sans-serif',
              fontSize: '14px',
            },
          },
        }}>
        <Box
          onClick={e => {
            e.stopPropagation();
            e.preventDefault();
          }}
          onDoubleClick={e => {
            e.stopPropagation();
            e.preventDefault();
          }}
          onKeyDown={e => e.preventDefault()}
          onFocus={e => e.target.blur()}
          onMouseDown={e => {
            e.stopPropagation();
            e.preventDefault();
          }}
          sx={{
            height: '100%',
            backgroundColor: getBackgroundColor(),
            opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
            textDecoration: isDeleted
              ? DELETED_CELL_STYLES.textDecoration
              : 'none',
            alignContent: 'center',
            paddingLeft: '8px',
          }}>
          <CellValue value={value} noLink={true} />
        </Box>
      </Tooltip>
    );
  }

  return (
    <Tooltip
      title="Click to edit"
      enterDelay={1000}
      enterNextDelay={1000}
      leaveDelay={0}
      placement="top"
      slotProps={{
        tooltip: {
          sx: {
            fontFamily: '"Source Sans Pro", sans-serif',
            fontSize: '14px',
          },
        },
      }}>
      <Box
        onClick={handleEditClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        sx={{
          ...cellViewingStyles,
          position: 'relative',
          cursor: 'pointer',
          backgroundColor: getBackgroundColor(),
          opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
          textDecoration: isDeleted
            ? DELETED_CELL_STYLES.textDecoration
            : 'none',
          borderLeft: '1px solid transparent',
          borderRight: '1px solid transparent',
          '&:hover': {
            borderLeft: '1px solid #DFE0E2',
            borderRight: '1px solid #DFE0E2',
          },
          ...(isEditing && {
            border: '2px solid rgb(77, 208, 225)',
            backgroundColor: 'rgba(77, 208, 225, 0.2)',
          }),
        }}>
        <span style={{flex: 1, position: 'relative', overflow: 'hidden'}}>
          {value}
          {isEditing}
        </span>
        {isHovered && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              opacity: 0,
              transition: 'opacity 0.2s ease',
              cursor: 'pointer',
              animation: 'fadeIn 0.2s ease forwards',
              '@keyframes fadeIn': {
                from: {opacity: 0},
                to: {opacity: 0.5},
              },
              '&:hover': {
                opacity: 0.8,
              },
            }}>
            {isEdited ? (
              <Button
                icon="undo"
                onClick={handleRevert}
                variant="secondary"
                size="small"
                style={{padding: '2px 4px', minWidth: 0}}
                tooltip="Revert to original value"
              />
            ) : (
              <Icon name="pencil-edit" height={14} width={14} />
            )}
          </Box>
        )}
      </Box>
    </Tooltip>
  );
};

export interface CellEditingRendererProps extends GridRenderEditCellParams {
  serverValue?: string;
  preserveFieldOrder?: (row: any) => any;
}

const NumberEditor: React.FC<{
  value: number;
  onClose: () => void;
  api: any;
  id: string | number;
  field: string;
  serverValue?: any;
}> = ({value, onClose, api, id, field, serverValue}) => {
  const [inputValue, setInputValue] = useState(value.toString());
  const {setEditedRows, setAddedRows, setFieldEdited} = useDatasetEditContext();

  const handleValueUpdate = (newValue: string) => {
    setInputValue(newValue);
    if (newValue !== '') {
      const numValue = Number(newValue);
      api.setEditCellValue({id, field, value: numValue});
    }
  };

  const handleBlur = () => {
    if (inputValue !== '') {
      const numValue = Number(inputValue);
      const existingRow = api.getRow(id);
      const isValueChanged = numValue !== serverValue;

      if (existingRow.___weave?.isNew) {
        setAddedRows((prev: Map<string, DatasetRow>) => {
          const newMap = new Map(prev);
          const updatedRow = {...existingRow};
          updatedRow[field] = numValue;
          newMap.set(existingRow.___weave?.id, updatedRow);
          return newMap;
        });
      } else {
        const updatedRow = {...existingRow};
        updatedRow[field] = numValue;
        setEditedRows((prev: Map<number, DatasetRow>) => {
          const newMap = new Map(prev);
          newMap.set(existingRow.___weave?.index, updatedRow);
          return newMap;
        });
        if (isValueChanged && existingRow.___weave?.index !== undefined) {
          setFieldEdited(existingRow.___weave.index, field, isValueChanged);
        }
      }
    }
    onClose();
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        height: '100%',
        width: '100%',
        border: '2px solid rgb(77, 208, 225)',
        backgroundColor: 'rgba(77, 208, 225, 0.2)',
      }}>
      <input
        type="number"
        value={inputValue}
        onChange={e => handleValueUpdate(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            handleBlur();
          } else if (e.key === 'Enter') {
            handleBlur();
          }
        }}
        onBlur={handleBlur}
        autoFocus
        style={{
          width: '100%',
          height: '100%',
          border: 'none',
          outline: 'none',
          background: 'none',
          textAlign: 'left',
          padding: '8px 12px',
          fontFamily: 'inherit',
          fontSize: 'inherit',
          color: 'inherit',
        }}
      />
    </Box>
  );
};

const StringEditor: React.FC<{
  value: string;
  serverValue?: string;
  onClose: () => void;
  params: GridRenderCellParams;
}> = ({value, serverValue, onClose, params}) => {
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const [hasInitialFocus, setHasInitialFocus] = useState(false);
  const initialWidth = React.useRef<number>();
  const initialHeight = React.useRef<number>();
  const [editorMode, setEditorMode] = useState<EditorMode>('text');
  const [editedValue, setEditedValue] = useState(value);

  const handleEditorModeChange = (newMode: EditorMode) => {
    setEditorMode(newMode);
    initialWidth.current = getPopoverWidth(newMode);
    initialHeight.current = getPopoverHeight();
  };

  const handleValueChange = (newValue: string) => {
    setEditedValue(newValue);
    params.api.setEditCellValue({
      id: params.id,
      field: params.field,
      value: newValue,
    });
  };

  const getPopoverWidth = useCallback(
    (mode: EditorMode = editorMode) => {
      const screenWidth = window.innerWidth;
      const maxWidth = screenWidth - 48;
      const minWidth = 400;
      const valueLength = typeof value === 'string' ? value.length : 0;
      const approximateWidth = Math.min(
        Math.max(valueLength, minWidth),
        maxWidth
      );
      return mode === 'diff'
        ? Math.min(approximateWidth * 2, maxWidth)
        : approximateWidth;
    },
    [editorMode, value]
  );

  const getPopoverHeight = useCallback(() => {
    const width = getPopoverWidth();
    const charsPerLine = Math.floor(width / 8);
    const lines =
      typeof value === 'string'
        ? value.split('\n').reduce((acc, line) => {
            return acc + Math.ceil(line.length / charsPerLine);
          }, 0)
        : 1;

    const maxHeight = Math.min(window.innerHeight / 2, 400);
    const contentHeight = Math.min(Math.max(lines * 24 + 80, 120), maxHeight);
    return contentHeight;
  }, [value, getPopoverWidth]);

  React.useLayoutEffect(() => {
    const element = document.activeElement?.closest('.MuiDataGrid-cell');
    if (element) {
      setAnchorEl(element as HTMLDivElement);
      if (!initialWidth.current) {
        initialWidth.current = getPopoverWidth();
      }
      if (!initialHeight.current) {
        initialHeight.current = getPopoverHeight();
      }
    }
  }, [getPopoverWidth, getPopoverHeight]);

  React.useEffect(() => {
    if (!hasInitialFocus) {
      setTimeout(() => {
        const textarea = inputRef.current?.querySelector('textarea');
        if (textarea) {
          textarea.focus();
          textarea.setSelectionRange(0, textarea.value.length);
          setHasInitialFocus(true);
        }
      }, 0);
    }
  }, [hasInitialFocus]);

  const renderEditor = () => {
    switch (editorMode) {
      case 'text':
        return (
          <TextEditor
            value={editedValue}
            onChange={handleValueChange}
            onClose={onClose}
            inputRef={inputRef}
          />
        );
      case 'code':
        return (
          <CodeEditor
            value={editedValue}
            onChange={handleValueChange}
            onClose={onClose}
          />
        );
      case 'diff':
        return (
          <DiffEditor
            value={editedValue}
            originalValue={serverValue ?? ''}
            onChange={handleValueChange}
            onClose={onClose}
          />
        );
    }
  };

  return (
    <>
      <CellViewingRenderer {...params} isEditing />
      <EditPopover
        anchorEl={anchorEl}
        onClose={onClose}
        initialWidth={initialWidth.current}
        initialHeight={initialHeight.current}
        editorMode={editorMode}
        setEditorMode={handleEditorModeChange}>
        {renderEditor()}
      </EditPopover>
    </>
  );
};

export const CellEditingRenderer: React.FC<
  CellEditingRendererProps
> = props => {
  const {setEditedRows, setAddedRows} = useDatasetEditContext();
  const {id, value, field, api, serverValue, preserveFieldOrder} = props;

  // Convert edit params to render params
  const renderParams: GridRenderCellParams = {
    ...props,
    value,
  };

  const updateRow = useCallback(
    (existingRow: any, newValue: any) => {
      const baseRow = {...existingRow};
      baseRow[field] = newValue;
      return preserveFieldOrder ? preserveFieldOrder(baseRow) : baseRow;
    },
    [field, preserveFieldOrder]
  );

  // For boolean values, don't show edit mode at all
  if (typeof value === 'boolean') {
    return null;
  }

  // For numeric values, show number editor
  if (typeof value === 'number') {
    return (
      <NumberEditor
        value={value}
        onClose={() => api.stopCellEditMode({id, field})}
        api={api}
        id={id}
        field={field}
        serverValue={serverValue}
      />
    );
  }

  // Text editor with popover for string values
  return (
    <StringEditor
      value={value as string}
      serverValue={serverValue}
      onClose={() => {
        const existingRow = api.getRow(id);
        const updatedRow = updateRow(existingRow, value);

        const isValueChanged = value !== serverValue;
        const rowToUpdate = {...updatedRow};

        if (existingRow.___weave?.isNew) {
          setAddedRows(prev => {
            const newMap = new Map(prev);
            newMap.set(existingRow.___weave?.id, rowToUpdate);
            return newMap;
          });
        } else {
          if (!rowToUpdate.___weave.editedFields) {
            rowToUpdate.___weave.editedFields = new Set<string>();
          }

          if (isValueChanged) {
            rowToUpdate.___weave.editedFields.add(field);
          } else {
            rowToUpdate.___weave.editedFields.delete(field);
          }

          setEditedRows(prev => {
            const newMap = new Map(prev);

            // If we don't have any edited fields and it's not a new row,
            // don't add it to the editedRows map
            if (rowToUpdate.___weave.editedFields.size === 0) {
              newMap.delete(existingRow.___weave?.index);
            } else {
              newMap.set(existingRow.___weave?.index, rowToUpdate);
            }

            return newMap;
          });
        }
        api.stopCellEditMode({id, field});
      }}
      params={renderParams}
    />
  );
};

export interface ControlCellProps {
  params: GridRenderCellParams;
  deleteRow: (index: number) => void;
  deleteAddedRow: (id: string) => void;
  restoreRow: (index: number) => void;
  isDeleted: boolean;
  isNew: boolean;
  hideRemoveForAddedRows?: boolean;
  disableNewRowHighlight?: boolean;
}

export const ControlCell: React.FC<ControlCellProps> = ({
  params,
  deleteRow,
  deleteAddedRow,
  restoreRow,
  isDeleted,
  isNew,
  hideRemoveForAddedRows,
  disableNewRowHighlight = false,
}) => {
  const rowId = params.id as string;
  const rowIndex = params.row.___weave?.index;

  // Hide remove button for added rows if requested
  if (isNew && hideRemoveForAddedRows) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          width: '100%',
          backgroundColor: disableNewRowHighlight
            ? CELL_COLORS.TRANSPARENT
            : CELL_COLORS.NEW,
        }}
      />
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        width: '100%',
        backgroundColor: isDeleted
          ? CELL_COLORS.DELETED
          : isNew && !disableNewRowHighlight
          ? CELL_COLORS.NEW
          : CELL_COLORS.TRANSPARENT,
        opacity: isDeleted ? DELETED_CELL_STYLES.opacity : 1,
        textDecoration: isDeleted ? DELETED_CELL_STYLES.textDecoration : 'none',
      }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: 1,
          transition: 'opacity 200ms ease',
          '.MuiDataGrid-row:not(:hover) &': {
            opacity: 0,
          },
          zIndex: 1000,
          backgroundColor: 'transparent',
        }}>
        {isDeleted ? (
          <Button
            onClick={() => restoreRow(rowIndex)}
            tooltip="Restore"
            icon="undo"
            size="small"
            variant="secondary"
          />
        ) : (
          <Button
            onClick={() =>
              isNew ? deleteAddedRow(rowId) : deleteRow(rowIndex)
            }
            tooltip="Delete"
            icon="delete"
            size="small"
            variant="secondary"
          />
        )}
      </Box>
    </Box>
  );
};

export interface ControlsColumnHeaderProps {
  onAddRow: () => void;
}

export const ControlsColumnHeader: React.FC<ControlsColumnHeaderProps> = ({
  onAddRow,
}) => (
  <Box
    sx={{
      margin: '2px',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100%',
    }}>
    <Button
      icon="add-new"
      onClick={onAddRow}
      variant="ghost"
      size="small"
      tooltip="Add row"
    />
  </Box>
);
