import React, {useEffect, useRef} from 'react';
import {twMerge} from 'tailwind-merge';

import {useDeepMemo} from '../../../../../hookUtils';
import {Button} from '../../../../Button';
import {TooltipHint} from '../../../../DraggablePopups';
import {TextField} from '../../../../Form/TextField';
import {Tailwind} from '../../../../Tailwind';
import {Timestamp} from '../../../../Timestamp';
import {Feedback} from '../pages/wfReactInterface/traceServerClient';

type NotesProps = {
  notes: Feedback[];
  viewer?: string | null;
  readonly: boolean;
  note?: string;
  setNote?: (value: string) => void;
  onNoteAdded?: () => void;
  onClick?: () => void;
  onClose?: () => void;
};

export const Notes = ({
  notes,
  viewer,
  readonly,
  note,
  setNote,
  onNoteAdded,
  onClick,
  onClose,
}: NotesProps) => {
  const isPreview = !onNoteAdded;
  const onChange = setNote
    ? (value: string) => {
        setNote(value);
      }
    : undefined;
  const onKeyDown = onNoteAdded
    ? (key: string) => {
        if (key === 'Enter') {
          onNoteAdded();
        }
      }
    : undefined;

  // Scroll notes on bottom into view
  const deepNotes = useDeepMemo(notes);
  const endOfNotesRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!isPreview && endOfNotesRef.current) {
      endOfNotesRef.current.scrollIntoView({behavior: 'smooth'});
    }
  }, [isPreview, deepNotes]);

  return (
    <Tailwind>
      <div
        onClick={onClick}
        className={twMerge(
          'flex max-w-[600px] flex-col',
          isPreview ? 'max-h-[200px] cursor-pointer' : 'px-16 py-12'
        )}
        style={{minWidth: 200}}>
        <div className="flex items-center">
          <div className="flex-1 basis-auto font-semibold">Notes</div>
          {onClose && (
            <Button
              size="small"
              variant="ghost"
              icon="close"
              tooltip="Close"
              onClick={onClose}
            />
          )}
        </div>
        {notes.length > 0 && (
          <div
            style={{maxHeight: 480}}
            className="mt-12 flex flex-col gap-16 overflow-auto">
            {notes.map(n => {
              const creator = n.creator ?? n.wb_user_id;
              return (
                <div key={n.id} className="flex items-start">
                  <div className="ml-12">
                    <div>
                      <span className="mr-8 font-semibold">{creator}</span>
                      <span
                        className={twMerge(
                          'text-moon-500',
                          isPreview ? '' : 'text-sm'
                        )}>
                        <Timestamp value={n.created_at} format="relative" />
                      </span>
                    </div>
                    <div className="text-moon-800">{n.payload.note}</div>
                  </div>
                </div>
              );
            })}
            <div ref={endOfNotesRef} />
          </div>
        )}
        {readonly ? null : onNoteAdded ? (
          <div className="mt-8 flex">
            <div className="ml-12 w-full">
              <TextField
                placeholder="Add a note"
                onKeyDown={onKeyDown}
                onChange={onChange}
                value={note}
                autoFocus
              />
            </div>
          </div>
        ) : (
          <div className="mt-8 text-center">
            <TooltipHint>Click to enlarge or add notes</TooltipHint>
          </div>
        )}
      </div>
    </Tailwind>
  );
};
