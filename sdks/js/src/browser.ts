// Re-export browser-safe modules
export {
  init,
  login,
  requireCurrentCallStackEntry,
  requireCurrentChildSummary,
} from './clientApi';
export {Dataset} from './dataset';
export {Evaluation} from './evaluation';
export {CallSchema, CallsFilter} from './generated/traceServerApi';
export {weaveAudio, weaveImage} from './media';
export {op} from './op';
export * from './types';
export {WeaveObject} from './weaveObject';

// Create a namespace-like object to match the cliProgress import
const cliProgress = {
  SingleBar: class SingleBar {
    constructor(_opt?: any, _preset?: any) {}
    start(_total: number, _startValue: number, _payload?: object) {}
    update(_current: number | object, _payload?: object) {}
    stop() {}
    increment(_step?: number, _payload?: object) {}
    render() {}
    isActive = false;
    getProgress() { return 0; }
    getTotal() { return 0; }
    setTotal(_total: number) {}
    updateETA() {}
  },
  
  MultiBar: class MultiBar {
    constructor(_opt?: any, _preset?: any) {}
    create(_total: number, _startValue: number, _payload?: any, _barOptions?: any) { 
      return new cliProgress.SingleBar(); 
    }
    remove(_bar: any) { return true; }
    update() {}
    stop() {}
    log(_data: string) {}
    isActive = false;
  },

  Presets: {
    legacy: { barCompleteChar: '', barIncompleteChar: '', format: '' },
    rect: { barCompleteChar: '', barIncompleteChar: '', format: '' },
    shades_classic: { barCompleteChar: '', barIncompleteChar: '', format: '' },
    shades_grey: { barCompleteChar: '', barIncompleteChar: '', format: '' },
  }
};

// Export the namespace
export default cliProgress;

// Note: cli-progress and OpenAI integration are excluded for browser builds 