<!-- Start SDK Example Usage [usage] -->
```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.service.getHealth();

  // Handle the result
  console.log(result);
}

run();

```
<!-- End SDK Example Usage [usage] -->