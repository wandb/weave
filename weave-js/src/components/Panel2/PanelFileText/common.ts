export const EXTENSION_INFO: {[key: string]: string} = {
  log: 'text',
  text: 'text',
  txt: 'text',
  markdown: 'markdown',
  md: 'markdown',
  patch: 'diff',
  ipynb: 'python',
  py: 'python',
  yml: 'yaml',
  yaml: 'yaml',
  xml: 'xml',
  html: 'html',
  htm: 'html',
  json: 'json',
  css: 'css',
  js: 'js',
  sh: 'sh',
};

export const inputType = {
  type: 'union' as const,
  members: Object.keys(EXTENSION_INFO).map(ext => ({
    type: 'file' as const,
    extension: ext,
    wbObjectType: 'none' as const,
  })),
};

export const processTextForDisplay = (
  fileExtension: string,
  text: string,
  lineLengthLimit: number,
  totalLinesLimit: number
) => {
  let lines = text?.split?.('\n');
  let truncatedLineLength = false;
  let truncatedTotalLines = false;

  // Pretty-print JSON
  if (
    (fileExtension === 'json' && lines.length === 1) ||
    (lines.length === 2 && lines[1] === '')
  ) {
    try {
      const parsed = JSON.parse(lines[0]);
      lines = JSON.stringify(parsed, undefined, 2)?.split?.('\n');
    } catch {
      // ok
    }
  }

  if (fileExtension === 'ipynb') {
    try {
      const parsed = JSON.parse(text);
      let normalized = '';
      parsed.cells.forEach((cell: any) => {
        normalized += '# %%\n';
        normalized += cell.source.join('') + '\n';
      });
      lines = normalized.split('\n');
    } catch {
      // ok
    }
  }

  // Truncate long lines
  lines = lines.map(line => {
    if (line.length > lineLengthLimit) {
      truncatedLineLength = true;
      return (
        line.slice(0, lineLengthLimit) +
        ` ... (line truncated to ${lineLengthLimit} characters)`
      );
    } else {
      return line;
    }
  });

  if (lines.length > totalLinesLimit) {
    truncatedTotalLines = true;
    lines = [
      ...lines.slice(0, totalLinesLimit),
      '...',
      `(truncated to ${totalLinesLimit} lines)`,
    ];
  }

  return {
    text: lines.join('\n'),
    truncatedLineLength,
    truncatedTotalLines,
  };
};
