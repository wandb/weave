import fs from 'fs';
import os from 'os';
import path from 'path';
import {fork} from 'child_process';
import {reset} from '../../utils/commonJSLoader';

describe('require("openai") instrumentation in child process', () => {
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openai-fork-test-'));
    // create fake openai module
    const modDir = path.join(tmpDir, 'node_modules', 'openai');
    fs.mkdirSync(modDir, {recursive: true});
    fs.writeFileSync(
      path.join(modDir, 'package.json'),
      JSON.stringify({name: 'openai', version: '4.0.0'})
    );
    const file = `
      class OpenAI {}
      OpenAI.prototype.chat = {
        completions: {
          create: async (params) => ({result: params})
        }
      };
      module.exports = { OpenAI, default: { OpenAI } };
    `;
    fs.writeFileSync(path.join(modDir, 'index.js'), file);
  });

  afterEach(() => {
    reset();
    fs.rmSync(tmpDir, {recursive: true, force: true});
  });

  test('patchedRequire is called in child process', done => {
    const childPath = path.join(tmpDir, 'openaiRequire.forkChild.js');
    // Use the compiled JavaScript paths from dist directory
    const instrumentationsPath = path.resolve(
      __dirname,
      '../../../dist/integrations/instrumentations.js'
    );
    const commonJSLoaderPath = path.resolve(
      __dirname,
      '../../../dist/utils/commonJSLoader.js'
    );
    fs.writeFileSync(
      childPath,
      `console.log('Starting child process...');
require('${commonJSLoaderPath}');
console.log('CommonJS loader loaded');
require('${instrumentationsPath}');
console.log('Instrumentations loaded');

// Add instrumentation for OpenAI
const {addInstrumentation} = require('${instrumentationsPath}');
addInstrumentation({
  moduleName: 'openai',
  subPath: 'index.js',
  version: '4.0.0',
  hook: (exports, name, baseDir) => {
    console.log('Instrumentation hook called for OpenAI');
    const proto = exports.OpenAI.prototype;
    if (
      proto.chat &&
      proto.chat.completions &&
      typeof proto.chat.completions.create === 'function'
    ) {
      const originalCreate = proto.chat.completions.create;
      proto.chat.completions.create = async function(params) {
        console.log('OpenAI create called with params:', JSON.stringify(params));
        const result = await originalCreate.call(this, params);
        console.log('OpenAI create returned:', JSON.stringify(result));
        return result;
      };
    }
    return exports;
  }
});
console.log('OpenAI instrumentation added');

const {OpenAI} = require('openai');
console.log('OpenAI module loaded');
const client = new OpenAI();
client.chat.completions.create({messages: [{role: 'user', content: 'test'}]}).then(result => {
  console.log('OpenAI create final result:', JSON.stringify(result));
  process.exit(0);
});
`
    );
    const child = fork(childPath, [], {
      cwd: tmpDir,
      env: {
        ...process.env,
        NODE_PATH:
          path.join(tmpDir, 'node_modules') +
          (process.env.NODE_PATH ? path.delimiter + process.env.NODE_PATH : ''),
      },
      stdio: ['ignore', 'pipe', 'pipe', 'ipc'],
    });
    let output = '';
    if (child.stdout) {
      child.stdout.on('data', data => {
        output += data.toString();
      });
    }
    child.on('exit', code => {
      console.log('Child process exited with code:', code);
      fs.unlinkSync(childPath);
      expect(output).toMatch(/Instrumentation hook called for OpenAI/);
      expect(output).toMatch(/OpenAI create final result:.*\{.*"result".*\}/);
      done();
    });
  });
});
