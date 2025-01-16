import {Wandb} from "./src";

const wandb = new Wandb({
  security: {
    username:
      process.env["WANDB_USERNAME"] ??
      "21c48d5af48839249a5089d852ed2b3cceb897d6",
    password:
      process.env["WANDB_PASSWORD"] ??
      "21c48d5af48839249a5089d852ed2b3cceb897d6",
  },
});

async function run() {
  const startResult = await wandb.calls.start({
    start: {
      projectId: "megatruong/codegen1",
      displayName: "hmmmmmm",
      opName: "test",
      startedAt: new Date(),
      attributes: {someAttr: "someValue", version: "1.0.0"},
      inputs: {test: 123, test2: "hello!"},
    },
  });
  console.log(startResult);

  const endResult = await wandb.calls.end({
    end: {
      projectId: "megatruong/codegen1",
      id: startResult.id,
      endedAt: new Date(),
      output: {this: {is: "nested"}},
      summary: {
        additionalProperties: {},
      },
    },
  });

  // Handle the result
  console.log(endResult);
}

run();
