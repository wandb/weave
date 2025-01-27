/**
 * Show code in the Monaco editor. If code has changed show a diff.
 */

import {DiffEditor, Editor} from '@monaco-editor/react';
import {Box} from '@mui/material';
import React from 'react';

import {sanitizeString} from '../../../../../util/sanitizeSecrets';
import {Loading} from '../../../../Loading';
import {useWFHooks} from '../pages/wfReactInterface/context';
import {detectLanguage} from './CodeView';

type CodeDiffProps = {
  oldValueRef: string;
  newValueRef: string;
  maxLines?: number;
};

const DEFAULT_MAX_LINES = 20;

export const CodeDiff = ({
  oldValueRef,
  newValueRef,
  maxLines,
}: CodeDiffProps) => {
  const {
    derived: {useCodeForOpRef},
  } = useWFHooks();
  const opContentsQueryOld = useCodeForOpRef(oldValueRef);
  const opContentsQueryNew = useCodeForOpRef(newValueRef);
  const textOld = opContentsQueryOld.result ?? '';
  const textNew = opContentsQueryNew.result ?? '';
  const loading = opContentsQueryOld.loading || opContentsQueryNew.loading;

  if (loading) {
    return <Loading centered size={25} />;
  }

  const sanitizedOld = sanitizeString(textOld);
  const sanitizedNew = sanitizeString(textNew);
  const languageOld = detectLanguage(oldValueRef, sanitizedOld);
  const languageNew = detectLanguage(newValueRef, sanitizedNew);

  const inner =
    sanitizedOld !== sanitizedNew ? (
      <DiffEditor
        height="100%"
        originalLanguage={languageOld}
        modifiedLanguage={languageNew}
        loading={loading}
        original={sanitizedOld}
        modified={sanitizedNew}
        options={{
          readOnly: true,
          minimap: {enabled: false},
          scrollBeyondLastLine: false,
          scrollbar: {
            handleMouseWheel: true, // Make horizontal scrolling with wheel work
            alwaysConsumeMouseWheel: false, // Don't capture page scroll
          },
          padding: {top: 10, bottom: 10},
          renderSideBySide: false,
        }}
      />
    ) : (
      <Editor
        height="100%"
        language={languageNew}
        loading={loading}
        value={sanitizedNew}
        options={{
          readOnly: true,
          minimap: {enabled: false},
          scrollBeyondLastLine: false,
          scrollbar: {
            handleMouseWheel: true, // Make horizontal scrolling with wheel work
            alwaysConsumeMouseWheel: false, // Don't capture page scroll
          },
          padding: {top: 10, bottom: 10},
        }}
      />
    );

  const totalLines = sanitizedNew.split('\n').length ?? 0;
  const showLines = Math.min(totalLines, maxLines ?? DEFAULT_MAX_LINES);
  const lineHeight = 18;
  const padding = 20;
  const height = showLines * lineHeight + padding + 'px';
  return <Box sx={{height}}>{inner}</Box>;
};
