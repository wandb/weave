// Helper namespace for using the nglviewer molecule renderer

// Warning: This namespace imports three.js which is a heavy dependency,
//          we should only import this namespace as an async module so
//          we don't pollute the main package with unneeded dependencies
import * as NGL from 'ngl';

import {RepresentationType} from '../types/libs/nglviewer';

//  Create one global stage so we don't consume too many resources
let stageSingleton: NGL.Stage | undefined;
let stageElement: HTMLDivElement | undefined;

export let getStage = (size: {width: number; height: number}) => {
  const {width, height} = size;
  //  Instantiate globals on first use
  if (stageElement == null) {
    stageElement = document.createElement('div');
  }
  stageElement.style.width = width.toString();
  stageElement.style.height = height.toString();
  if (stageSingleton == null) {
    stageSingleton = new NGL.Stage(stageElement, {
      backgroundColor: 'white',
      tooltip: false,
    }) as NGL.Stage;
  }

  const w = size.width.toString();
  const h = size.height.toString();
  stageSingleton.setSize(w, h);

  return stageSingleton;
};

export let moleculeStage = (
  domElement: HTMLElement,
  path: Blob | File | string,
  size: {width: number; height: number},
  settings: {representation?: RepresentationType},
  fileExt: string
) => {
  const w = size.width.toString();
  const h = size.height.toString();
  domElement.style.width = w;
  domElement.style.height = h;
  domElement.getBoundingClientRect = () =>
    new DOMRect(0, 0, size.width, size.height);
  const stage: NGL.Stage = new NGL.Stage(domElement);
  stage.setSize(w, h);
  stage
    .loadFile(path, fileExt)
    .then(o => {
      // Cleanup
      stage.eachRepresentation(r => r.dispose());
      if (settings.representation && settings.representation !== 'default') {
        o.addRepresentation(settings.representation);
      } else {
        stage.defaultFileRepresentation(o);
      }
      o.autoView();
      stage.autoView();
      const pa = o.structure.getPrincipalAxes();
      stage.animationControls.rotate(pa.getRotationQuaternion(), 0);

      return o;
    })
    .catch(e => {
      console.log('molecule screenshot error', e);
    });

  return stage;
};

class StageManager {
  stageListeners: Array<{
    resolve: (s: NGL.Stage) => void;
    domElement: HTMLElement;
  }>;
  activeStages: number;
  maxOpenStages: number;

  constructor(maxOpenStages: number = 6) {
    this.stageListeners = [];
    this.maxOpenStages = maxOpenStages;
    this.activeStages = 0;
  }
  requestStage(domElement: HTMLElement) {
    return new Promise<NGL.Stage>(resolve => {
      if (this.activeStages < this.maxOpenStages) {
        this.activeStages++;
        resolve(this._makeDisposableStage(domElement));
      } else {
        this.stageListeners.push({resolve, domElement});
      }
    });
  }

  _disposeStage(stage: any) {
    stage.__dispose();
    this.activeStages--;
    if (this.stageListeners.length > 0) {
      const listener = this.stageListeners.pop();
      if (listener != null) {
        this.activeStages++;
        listener.resolve(this._makeDisposableStage(listener.domElement));
      }
    }
  }

  _makeDisposableStage(domElement: HTMLElement) {
    const stage = new NGL.Stage(domElement);
    (stage as any).__dispose = stage.dispose.bind(stage);
    stage.dispose = () => {
      this._disposeStage(stage);
    };
    return stage;
  }
}

const stageManagerSingleton = new StageManager();
export let moleculeScreenshot = async (
  path: Blob | File | string,
  size: {width: number; height: number},
  settings: {representation?: RepresentationType},
  fileExt: string
) => {
  const domElement = document.createElement('div');

  // Set Size
  // NOTE:
  // 1) We need to render offscreen. This doesn't work in ngl
  // , but only because they use getBoundingClientRect to get size
  // By spoofing getBoundingClientRect we can create our own offscreen
  // renderer with NGL.
  //
  // 2) NGL creates it canvas size based on the initial dom element.
  // Using a non-integer as the factor argument to ngl fails for non-integers.
  // So instead we adjust the size of the based element based on pixel ratio
  const pr = window.devicePixelRatio;
  domElement.getBoundingClientRect = () =>
    new DOMRect(0, 0, size.width * pr, size.height * pr);
  const w = size.width.toString();
  const h = size.height.toString();
  domElement.style.width = w;
  domElement.style.height = h;
  const stage: NGL.Stage = await stageManagerSingleton.requestStage(domElement);
  stage.setSize(w, h);

  return new Promise<Blob>((res, rej) =>
    stage
      .loadFile(path, fileExt)
      .then(async o => {
        if (settings.representation && settings.representation !== 'default') {
          o.addRepresentation(settings.representation);
        } else {
          stage.defaultFileRepresentation(o);
        }

        o.autoView();
        stage.autoView();
        const pa = o.structure.getPrincipalAxes();
        stage.animationControls.rotate(pa.getRotationQuaternion(), 0);
        const image = await stage.makeImage({factor: 1});
        stage.dispose();
        return res(image);
      })
      .catch(e => {
        console.log('molecule screenshot error', e);
      })
  );
};
