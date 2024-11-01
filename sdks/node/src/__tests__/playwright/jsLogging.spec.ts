import {expect, test} from '@playwright/test';

test('defaults to JS page', async ({page}) => {
  test.setTimeout(5000);

  // TODO: We should really be calling the API here instead of going to this static link
  await page.goto(
    'https://wandb.ai/megatruong/examples/weave/traces?peekPath=/megatruong/examples/calls/0192c64a-253e-7604-867f-ed23a23ab14f'
  );

  // Nav to the "use" tab and confirm it's on the TypeScript page by default (not Python)
  await page.getByRole('tab', {name: 'use'}).click();
  await expect(page.getByText(`import * as weave from 'weave';`)).toBeVisible();
  await expect(page.getByText(`import weave`)).not.toBeVisible();
});
