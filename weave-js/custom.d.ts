/// <reference path="./custom-slate.d.ts"/>

/* This file is needed if you want to run tsc (the Typescript compiler)
   by itself, outside of the webpack build. Webpack must do something
   similar. */
declare module '*.svg' {
  export const ReactComponent: any;
  const content: any;
  export default content;
}

declare module '*.png' {
  const content: any;
  export default content;
}

declare module '*.gif' {
  const content: any;
  export default content;
}

declare module 'ngl' {
  declare class Stage {
    mouseObserver: MouseObserver;
    animationControls: AnimationControls;
    constructor(ele: HTMLElement, opts?: StageOptions);
    loadFile(
      path: string | File | Blob,
      fileExt: string
    ): Promise<StructureComponent>;
    makeImage(opts?: MakeImageOpts): Promise<Blob>;
    defaultFileRepresentation(o: StructureComponent): void;
    eachRepresentation(callback: (o: Representation) => void): void;
    autoView(): void;
    dispose(): void;
    setSize(width: string, height: string): void;
  }
}

declare module 'mdast-util-gfm/to-markdown';
declare module 'mdast-util-math';
declare module 'mdast-util-to-string';
declare module 'rehype-sanitize';
declare module 'remark-math';
declare module 'rehype-katex';
declare module 'rehype-parse';

declare module 'monaco-editor/esm/vs/editor/editor.main';
declare module 'monaco-editor/esm/vs/editor/editor.worker.js?worker&inline';
declare module 'monaco-editor/esm/vs/language/json/json.worker.js?worker&inline';
declare module 'monaco-yaml/lib/esm/yaml.worker.js?worker&inline';

declare module 'react-vis/dist/style.css?raw';

//
declare module 'react-vis/dist/style.css';

declare module '@segment/analytics.js-integration-segmentio';

// TODO: everything below is vendored from vite because we can't import their full
// types until we upgrade to TS 4.x
//
// when we upgrade, REMOVE ALL OF THIS except for the reference comment below (remove
// the fourth / character so that TS actually uses it):
//// <reference types="vite/client" />

interface ImportMeta {
  url: string;

  readonly hot?: {
    readonly data: any;

    accept(): void;
    accept(cb: (mod: any) => void): void;
    accept(dep: string, cb: (mod: any) => void): void;
    accept(deps: readonly string[], cb: (mods: any[]) => void): void;

    /**
     * @deprecated
     */
    acceptDeps(): never;

    dispose(cb: (data: any) => void): void;
    decline(): void;
    invalidate(): void;

    on: {
      (
        event: 'vite:beforeUpdate',
        cb: (payload: import('./hmrPayload').UpdatePayload) => void
      ): void;
      (
        event: 'vite:beforePrune',
        cb: (payload: import('./hmrPayload').PrunePayload) => void
      ): void;
      (
        event: 'vite:beforeFullReload',
        cb: (payload: import('./hmrPayload').FullReloadPayload) => void
      ): void;
      (
        event: 'vite:error',
        cb: (payload: import('./hmrPayload').ErrorPayload) => void
      ): void;
      <T extends string>(
        event: import('./customEvent').CustomEventName<T>,
        cb: (data: any) => void
      ): void;
    };
  };

  readonly env: ImportMetaEnv;

  glob(pattern: string): Record<
    string,
    () => Promise<{
      [key: string]: any;
    }>
  >;

  globEager(pattern: string): Record<
    string,
    {
      [key: string]: any;
    }
  >;
}

interface ImportMetaEnv {
  [key: string]: string | boolean | undefined;
  BASE_URL: string;
  MODE: string;
  DEV: boolean;
  PROD: boolean;
  SSR: boolean;
}
