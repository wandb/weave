import * as monacoEditor from 'monaco-editor/esm/vs/editor/editor.main';

// monaco-yaml needs monaco on the window before we load it, which is why
// we do this in a separate import

// the monaco react integration ALSO uses window.monaco to prevent loading
// a separate monaco, but this doesn't need to happen pre-bootstrap
(window as any).monaco = monacoEditor;
