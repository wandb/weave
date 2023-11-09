// Helper namespace for using the babylon.js rendering engine
// for rendering wandb supported types

// Warning: This namespace imports babylon which is a heavy dependency,
//          we should only import this namespace as an async module so
//          we don't pollute the main package with unneeded dependencies

// Babylon Imports
// Important!: Leave the unused babylonloader import.
// We don't call it's methods
// It adds support for the extra file types
import '@babylonjs/loaders';

import {
  Camera,
  Color3,
  Engine,
  MeshBuilder,
  Scene,
  StandardMaterial,
  Vector3,
} from '@babylonjs/core';
import * as Babylon from '@babylonjs/core';
import {AdvancedDynamicTexture} from '@babylonjs/gui';
import * as GUI from '@babylonjs/gui';
import * as BabylonViewer from '@babylonjs/viewer';
import _ from 'lodash';

import {Camera3DControl} from '../components/MediaCard';
import clamp from './clamp';
// Standard Imports
import {onNextExitFullscreen} from './fullscreen';
import {
  Category,
  getVertexCompatiblePositionsAndColors,
} from './SdkPointCloudToBabylon';
import {add, mag, mul, sub} from './vec3';

export type Position = [x: number, y: number, z: number];
export type RgbColor = [r: number, g: number, b: number];

export interface Vector {
  start: Position;
  end: Position;
  color: RgbColor;
}

export type Edge = [Vector3, Vector3];

export interface SceneBox {
  edges: Edge[];
  label?: string;
  color: RgbColor;
  score?: number;
}

// A point has color associated with it,
// position has only xyz
export interface ScenePoint {
  position: Position;
  color?: RgbColor;
  category?: Category;
}

export interface BabylonPointCloud {
  points: ScenePoint[];
  vectors: Vector[];
  boxes: SceneBox[];
}

interface RenderContext {
  canvas: HTMLCanvasElement;
  engine: Engine;
}

// This component uses one central engine and webgl context for performance
// and restrictions.
//
// WebGL is currently restricted to 16 max instances - October 30, 2019
// https://bugs.chromium.org/p/chromium/issues/detail?id=771792

// The fullscreen engine is mounted to the dom when
// fullscreen is requested
let fullscreenCanvas: HTMLCanvasElement | null = null;
let fullscreenEngine: Engine | null = null;

// The render engine is used internally to render screenshots
let renderCanvas: HTMLCanvasElement | null = null;
let renderEngine: Engine | null = null;

// TODO: Make this an async function that pulls off a queue
// Also make the render functions take callbacks instead of return promises
export let getRenderContext = () => {
  //  Instantiate globals on first use
  if (!renderCanvas) {
    renderCanvas = document.createElement('canvas');
    renderEngine = new Babylon.Engine(renderCanvas, undefined, {
      // ! Important: This must be here or screenshots will fail
      preserveDrawingBuffer: true,
    });
  }

  return {
    canvas: renderCanvas,
    engine: renderEngine,
  } as RenderContext;
};

export let getFullscreenContext = () => {
  //  Instantiate globals on first use
  if (!fullscreenCanvas) {
    fullscreenCanvas = document.createElement('canvas');
    fullscreenEngine = new Babylon.Engine(fullscreenCanvas, true);
  }

  fullscreenCanvas.width = window.screen.width;
  fullscreenCanvas.height = window.screen.height;

  return {
    canvas: fullscreenCanvas,
    engine: fullscreenEngine,
  } as RenderContext;
};

interface RenderRequestFull {
  // filePath: string;
  fullscreen?: boolean;
  width?: number;
  height?: number;
}

export interface RenderFullscreen {
  fullscreen: true;
  domElement: HTMLElement;
}

export interface RenderScreenshot {
  fullscreen?: false;
  width: number;
  height: number;
}

// Render request represents thek
export type RenderRequest<T> = RenderRequestFull & T;

export interface RenderResult<T> {
  context: RenderContext;
  camera: Camera;
  scene: Scene;
  request: RenderRequest<T>;
  cleanup?: () => any;
  viewer?: BabylonViewer.DefaultViewer;
}

// Returns a base64 encoded string
export async function renderScreenshot(
  renderResult: RenderResult<RenderScreenshot>
) {
  const {context, camera, request} = renderResult;
  const {engine, canvas} = context;

  const width = request.width * window.devicePixelRatio;
  const height = request.height * window.devicePixelRatio;

  return await new Promise<string>(async resolve => {
    // Use the viewer screenshot mechanism when using the
    // viewer to render
    if (renderResult.viewer) {
      renderResult.viewer.takeScreenshot(resolve, width, height);
    } else {
      renderResult.scene.executeWhenReady(() => {
        canvas.width = width;
        canvas.height = height;
        renderResult.scene.render();
        Babylon.Tools.CreateScreenshot(engine, camera, request.width, resolve);
      });
    }
  });
}

export async function renderFullscreen(result: RenderResult<RenderFullscreen>) {
  const {scene, context} = result;
  const {canvas, engine} = context;

  // canvas elements can't contain other html elements, so we create
  // a parent to hold other elements - this will allow us to put controls
  // onto the screen
  const fullScreenElement = document.createElement('div');
  fullScreenElement.style.height = '100%';
  fullScreenElement.style.width = '100%';

  result.request.domElement.appendChild(fullScreenElement);
  fullScreenElement.appendChild(canvas);
  canvas.width = window.screen.width;
  canvas.height = window.screen.height;
  scene.render();

  engine.runRenderLoop(() => {
    scene.render();
  });

  canvas.addEventListener('resize', () => {
    engine.resize();
  });

  onNextExitFullscreen(() => {
    canvas.remove();
  });

  try {
    await fullScreenElement.requestFullscreen();
  } catch (e) {
    throw new Error('Fullscreen request invalid: ' + e);
  }

  return {fullscreen: true};
}
interface Size {
  width: number;
  height: number;
}

function getSize(request: RenderRequest<unknown>): Size {
  if (request.fullscreen) {
    return {width: window.screen.width, height: window.screen.height};
  } else {
    const {width, height} = request as RenderScreenshot;
    return {width, height};
  }
}

export function renderJsonPoints<T>(
  pointCloud: BabylonPointCloud,
  request: RenderRequest<T>,
  meta?: Camera3DControl
): RenderResult<T> {
  const context = request.fullscreen
    ? getFullscreenContext()
    : getRenderContext();

  const {canvas} = context;

  const size = getSize(request);

  const scene = pointCloudScene(pointCloud, canvas, context, size, meta);
  const cleanup = () => scene.dispose();
  const camera = scene.cameras[0];

  // const camera = scene.cameras[0];

  return {camera, context, scene, request, cleanup};
}

const pointCloudScene = (
  pointCloud: BabylonPointCloud,
  canvas: HTMLCanvasElement,
  {engine}: RenderContext,
  {width, height}: {width: number; height: number},
  meta?: Camera3DControl
): Scene => {
  // these dimensions did not have a lot of thought put into them,
  // so they may need fine tuning. The idea is that table & media previews
  // are smaller than these dimensions.
  const isSmallView = width < 400 || height < 400;
  const scene = new Babylon.Scene(engine);

  const target = [0, 0, 0];

  const camera = new Babylon.ArcRotateCamera(
    'camera1',
    0,
    2,
    300,
    new Babylon.Vector3(...target),
    scene
  );

  camera.upVector = new Vector3(0, 0, 1);
  camera.attachControl(canvas, true, true);

  camera.maxZ = 32000000;
  camera.minZ = -32000000;
  camera.lowerRadiusLimit = 0.0001;
  camera.upperRadiusLimit = 800;

  camera.lowerBetaLimit = -800;
  camera.upperBetaLimit = 800;

  camera.lowerAlphaLimit = -800;
  camera.upperAlphaLimit = 800;

  // Tilt the camera slightly up
  camera.beta = 1.2;

  camera.panningSensibility = 100;

  /**** Beginning Camera Code *****/

  // Add event listener for custom camera controls
  let plane: Babylon.Plane;
  let pickOrigin: Vector3;
  let isPanning = false;

  // This camera moves more accurately than the base babylon.js camera
  // It aims to keep the mouse location fixed to a point in the scene
  // and drag from there
  scene.onPointerDown = evt => {
    if (evt.ctrlKey) {
      const pickResult = scene.pick(scene.pointerX, scene.pointerY);
      if (pickResult?.pickedMesh && pickResult?.pickedPoint) {
        const normal = camera.position
          .subtract(pickResult.pickedPoint)
          .normalize();
        plane = Babylon.Plane.FromPositionAndNormal(
          pickResult.pickedPoint,
          normal
        );
        pickOrigin = pickResult.pickedPoint;
        isPanning = true;
        camera.detachControl(canvas);
      }
    }
  };

  scene.onPointerUp = () => {
    isPanning = false;
    camera.attachControl(canvas, true, true);
    scene.render();
  };

  const identity = Babylon.Matrix.Identity();
  scene.onPointerMove = () => {
    if (isPanning) {
      const ray = scene.createPickingRay(
        scene.pointerX,
        scene.pointerY,
        identity,
        camera,
        false
      );
      const distance = ray.intersectsPlane(plane);

      if (distance === null) {
        return;
      }
      const pickedPoint = ray.direction.scale(distance).add(ray.origin);
      const diff = pickedPoint.subtract(pickOrigin);
      camera.target.subtractInPlace(diff);
      scene.render();
    }
  };

  scene.onKeyboardObservable.add((kbInfo: Babylon.KeyboardInfo) => {
    const incrementBy = 2;
    switch (kbInfo.type) {
      case Babylon.KeyboardEventTypes.KEYDOWN:
        const key = kbInfo.event.key;

        if (key === '-' || key === '=' || key === '+') {
          scene.meshes.forEach((mesh: Babylon.AbstractMesh) => {
            if (mesh.material && 'pointSize' in mesh.material) {
              if (key === '-') {
                mesh.material.pointSize = Math.max(
                  1,
                  mesh.material.pointSize - incrementBy
                );
              } else if (key === '+' || key === '=') {
                mesh.material.pointSize += incrementBy;
              }
            }
          });
        }
        break;
    }
  });

  /**** End of Camera Code ****/

  // Create a custom mesh
  const pcMesh = new Babylon.Mesh('custom', scene);

  const itemsInScene = [];

  // Make point cloud
  const vertexData = new Babylon.VertexData();

  // Assign positions
  const {positions, colors} = getVertexCompatiblePositionsAndColors(
    pointCloud.points
  );
  vertexData.positions = positions;
  vertexData.colors = colors;

  // Apply vertexData to custom mesh
  vertexData.applyToMesh(pcMesh);

  camera.parent = pcMesh;

  const pcMaterial = new Babylon.StandardMaterial('mat', scene);
  pcMaterial.emissiveColor = new Babylon.Color3(1, 1, 1);
  pcMaterial.disableLighting = true;
  pcMaterial.pointsCloud = true;

  // Adjust pixel size for larger rendering
  const sizeAdjustment = clamp(width / 200, {min: 0.4, max: 0.8});
  pcMaterial.pointSize = 3 * window.devicePixelRatio * sizeAdjustment;

  pcMesh.material = pcMaterial;
  itemsInScene.push(pcMesh);

  // Create a UI component to hold the labels
  const adt = AdvancedDynamicTexture.CreateFullscreenUI('UI', true, scene);

  camera.zoomOn([pcMesh]);

  // This is a hack that makes the zooming better on small scenes.
  //  We could spend time to scale this smoothly for a better result
  if (camera.radius < 20) {
    camera.wheelPrecision = 50;
  }

  pointCloud.vectors.forEach(v => {
    const p1 = v.start;
    const p2 = v.end;

    const diff = sub(p2, p1);
    const h = mag(diff);

    const arrowWidth = h / 70;
    const arrowBaseWidth = h / 40;

    const arrowBase = add(p1, mul(diff, 0.8));
    const path = [
      new Vector3(...p1),
      new Vector3(...arrowBase),
      new Vector3(...arrowBase),
      new Vector3(...p2),
    ];

    const arrow = MeshBuilder.CreateTube(
      p1.toString(),
      {
        path,
        radiusFunction: i => {
          if (i === 0 || i === 1) {
            return arrowWidth;
          } else if (i === 2) {
            return arrowBaseWidth;
          } else {
            // i === 3(last element)
            return 0;
          }
        },
      },
      scene
    );

    arrow.material = colorMat(
      v.color == null ? cyan3 : new Color3(...v.color),
      scene
    );
  });

  pointCloud.boxes.forEach((box, index) => {
    const {edges, color, label, score} = box;

    // Create lines
    const lines = MeshBuilder.CreateLineSystem('lines', {lines: edges}, scene);
    const center = _.flatten(edges)
      .reduce((cv, v) => cv.add(v))
      .divide(
        new Vector3(edges.length * 2, edges.length * 2, edges.length * 2)
      );

    // If we are iterating over camera, target a box
    if (index === meta?.cameraIndex) {
      camera.position = center.add(new Vector3(0, 0, 1000));
      camera.target = center;
      camera.zoomOn([lines]);
    }

    // the labels are not meaningful for smaller sizes
    // score of 0 is meaningful and should be displayed
    if ((label || score !== undefined) && !isSmallView) {
      const textToAdd = [];
      if (label) {
        textToAdd.push(label);
      }
      if (score !== undefined) {
        // deliberately always showing () around score to make it obvious what's score vs label
        textToAdd.push(`(${score})`);
      }
      const textBlock = new GUI.TextBlock();
      textBlock.text = textToAdd.join(' ');
      textBlock.color = 'white';
      textBlock.fontSize = 16;
      adt.addControl(textBlock);
      textBlock.linkWithMesh(lines);
      textBlock.linkOffsetY = -20;
    }

    lines.color = new Color3(...color);
  });

  itemsInScene.push(pcMesh);

  return scene;
};

export function renderViewer(domElement: HTMLElement, url: string) {
  const viewer = new BabylonViewer.DefaultViewer(domElement, {
    scene: {
      debug: false,
    },
    camera: {
      behaviors: {
        autoRotate: 0,
        framing: {
          type: 2,
          zoomOnBoundInfo: true,
          zoomStopsAnimation: false,
        },
      },
    },
    model: {url},
  });

  // HAX HAX HAXXXXXX: This is ridiculous.
  // Babylon inserts a GLOBAL STYLE via <style></style> when it renders its elements.
  // One of these accidentally-global injected styles is
  // span { display: inline-block; }
  // which breaks a ton of stuff (DUH).
  const navBarTemplate = viewer.templateManager.getTemplate('navBar') as any;
  navBarTemplate.onHTMLRendered.add(() => {
    const styleEl = domElement.querySelector('nav-bar style');
    if (styleEl == null) {
      return;
    }
    if (!/viewer nav-bar span\{/.test(styleEl.innerHTML)) {
      styleEl.innerHTML = styleEl.innerHTML.replace(
        'span{',
        'viewer nav-bar span{'
      );
    }
  });

  return viewer;
}

const cyan3 = new Color3(0, 255, 255);

const colorMat = (color: Color3, scene: Scene) => {
  const mat = new StandardMaterial('color', scene);
  mat.alpha = 1;
  mat.diffuseColor = color;
  mat.emissiveColor = color;
  mat.alpha = 1;

  return mat;
};
