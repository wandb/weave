# Files
(*files*)

## Overview

### Available Operations

* [create](#create) - File Create
* [content](#content) - File Content

## create

File Create

### Example Usage

```typescript
import { openAsBlob } from "node:fs";
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.files.create({
    file: await openAsBlob("example.file"),
    projectId: "<id>",
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { openAsBlob } from "node:fs";
import { WandbCore } from "wandb/core.js";
import { filesCreate } from "wandb/funcs/filesCreate.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await filesCreate(wandb, {
    file: await openAsBlob("example.file"),
    projectId: "<id>",
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useFilesCreateMutation
} from "wandb/react-query/filesCreate.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.BodyFileCreateFileCreatePost](../../models/components/bodyfilecreatefilecreatepost.md)                                                                             | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.FileCreateRes](../../models/components/filecreateres.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |

## content

File Content

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.files.content({
    projectId: "<id>",
    digest: "<value>",
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { filesContent } from "wandb/funcs/filesContent.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await filesContent(wandb, {
    projectId: "<id>",
    digest: "<value>",
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useFilesContentMutation
} from "wandb/react-query/filesContent.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.FileContentReadReq](../../models/components/filecontentreadreq.md)                                                                                                 | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[any](../../models/.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |