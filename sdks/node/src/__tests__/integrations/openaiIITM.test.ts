import fs from 'fs';
import os from 'os';
import path from 'path';
import {fork} from 'child_process';

describe('ESM Module instrumentation', () => {
  test('should apply the hook when module version is compatible', done => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openai-fork-test-'));
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

    // Use the compiled JavaScript paths from dist directory
    const instrumentationsPath = path.resolve(
      __dirname,
      '../../../dist/integrations/instrumentations.js'
    );
    const customInstrumentationFile = `
      // Add instrumentation for OpenAI
      const {addESMInstrumentation} = require('${instrumentationsPath}');
      addESMInstrumentation({
        moduleName: 'openai',
        version: '4.0.0',
        hook: (exports) => {
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
    `;
    const customInstrumentationPath = path.join(
      tmpDir,
      'customInstrumentation.js'
    );
    fs.writeFileSync(customInstrumentationPath, customInstrumentationFile);
    const esmLoaderPath = path.resolve(
      __dirname,
      '../../../dist/esm/instrument.js'
    );
    const childPath = path.join(tmpDir, 'openaiRequire.forkChild.mjs');
    fs.writeFileSync(
      childPath,
      `console.log('Starting child process...');

import {OpenAI} from 'openai';
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
      execArgv: [
        `--import=${customInstrumentationPath}`,
        `--import=${esmLoaderPath}`,
      ],
    });
    let output = '';
    if (child.stdout) {
      child.stdout.on('data', data => {
        output += data.toString();
      });
    }
    child.on('exit', code => {
      expect(code).toBe(0);
      fs.unlinkSync(childPath);
      fs.rmSync(tmpDir, {recursive: true, force: true});
      expect(output).toMatch(/Instrumentation hook called for OpenAI/);
      expect(output).toMatch(/OpenAI create final result:.*\{.*"result".*\}/);
      done();
    });
  });

  test('should not apply the hook when module version is incompatible', done => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'openai-fork-test-'));
    const modDir = path.join(tmpDir, 'node_modules', 'openai');
    fs.mkdirSync(modDir, {recursive: true});
    fs.writeFileSync(
      path.join(modDir, 'package.json'),
      JSON.stringify({name: 'openai', version: '3.0.0'})
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

    // Use the compiled JavaScript paths from dist directory
    const instrumentationsPath = path.resolve(
      __dirname,
      '../../../dist/integrations/instrumentations.js'
    );
    const customInstrumentationFile = `
      // Add instrumentation for OpenAI
      const {addESMInstrumentation} = require('${instrumentationsPath}');
      addESMInstrumentation({
        moduleName: 'openai',
        version: '4.0.0',
        hook: (exports) => {
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
    `;
    const customInstrumentationPath = path.join(
      tmpDir,
      'customInstrumentation.js'
    );
    fs.writeFileSync(customInstrumentationPath, customInstrumentationFile);
    const esmLoaderPath = path.resolve(
      __dirname,
      '../../../dist/esm/instrument.js'
    );
    const childPath = path.join(tmpDir, 'openaiRequire.forkChild.mjs');
    fs.writeFileSync(
      childPath,
      `console.log('Starting child process...');

import {OpenAI} from 'openai';
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
      execArgv: [
        `--import=${customInstrumentationPath}`,
        `--import=${esmLoaderPath}`,
      ],
    });
    let output = '';
    if (child.stdout) {
      child.stdout.on('data', data => {
        output += data.toString();
      });
    }
    child.on('exit', code => {
      expect(code).toBe(0);
      fs.unlinkSync(childPath);
      fs.rmSync(tmpDir, {recursive: true, force: true});
      expect(output).not.toMatch(/Patched OpenAI create called with params/);
      expect(output).toMatch(/OpenAI create final result:.*\{.*"result".*\}/);
      done();
    });
  });
});
