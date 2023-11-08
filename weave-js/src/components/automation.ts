import {useEffect} from 'react';

import getConfig from '../config';
import {useLoadWeaveObjects} from './Panel2/weaveBackend';

let activeAutomationId: string | null;

function timeout(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

interface ServerCommandRunJs {
  command: 'run_js';
  js: string;
}

interface ServerCommandEnd {
  command: 'end';
}

type ServerCommand = ServerCommandRunJs | ServerCommandEnd;

interface ServerCommandsResponse {
  commands: ServerCommand[];
}

function serverUrl() {
  const weaveExecuteUrl = new URL(getConfig().backendWeaveExecutionUrl());
  return weaveExecuteUrl.origin;
}

async function getCommands(automationId: string, seenCommands: number) {
  // eslint-disable-next-line wandb/no-unprefixed-urls
  return fetch(
    `${serverUrl()}/__weave/automate/${automationId}/commands_after/${seenCommands}`
  );
}

async function sendStatus(automationId: string, status: any) {
  // eslint-disable-next-line wandb/no-unprefixed-urls
  await fetch(`${serverUrl()}/__weave/automate/${automationId}/set_status`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(status),
  });
}

async function sendStatusOk(automationId: string) {
  sendStatus(automationId, {status: 0, message: 'ok'});
}

async function sendStatusError(automationId: string, message: string) {
  sendStatus(automationId, {status: 1, message});
}

export const useWeaveAutomation = (automationId: string | null) => {
  const {loading, remoteOpStore} = useLoadWeaveObjects();
  useEffect(() => {
    // We construct our own non-caching client to get around the cache
    // for now.
    if (loading || automationId == null) {
      return;
    }
    activeAutomationId = automationId;

    let shouldRun = true;
    let seenCommands = 0;

    const run = async () => {
      // Initial sleep to ensure UI is ready
      await timeout(1000);

      while (shouldRun) {
        // eslint-disable-next-line wandb/no-unprefixed-urls
        const rawResponse = await getCommands(automationId, seenCommands);
        if (rawResponse.status !== 200) {
          console.log('Weave automation protocol error: ', rawResponse);
          break;
        }
        const response: ServerCommandsResponse = await rawResponse.json();
        const serverCommands = response.commands;
        seenCommands += response.commands.length;
        for (const serverCommand of serverCommands) {
          console.log('Weave automation. New command:', serverCommand);
          if (serverCommand.command === 'run_js') {
            try {
              // TODO check this out
              // tslint:disable
              // eslint-disable-next-line no-eval
              eval(serverCommand.js);
              // tslint:enable
            } catch (e: any) {
              console.log('Weave automation. Error:', e);
              await sendStatusError(automationId, e.stack.toString());
              shouldRun = false;
              break;
            }
          } else if (serverCommand.command === 'end') {
            shouldRun = false;
            await sendStatusOk(automationId);
            break;
          } else {
            // Don't throw, send back an error!
            const message = 'Unhandle automation command: ' + serverCommand;
            console.error(message);
            await sendStatusError(automationId, message);
            shouldRun = false;
            break;
          }
          await timeout(1000);
        }
        // commands = serverCommands;
        await timeout(1000);
      }
      console.log('Weave automation. Exited automation loop.');
    };
    run();
    return () => {
      shouldRun = false;
    };
  }, [automationId, loading, remoteOpStore]);
};

export const onAppError = (message: string) => {
  if (activeAutomationId == null) {
    return;
  }
  sendStatusError(activeAutomationId, message);
};
