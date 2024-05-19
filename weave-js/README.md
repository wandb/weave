# @wandb/weave

This module contains the public-facing `@wandb/weave` library. This code used to live in app, but was moved here so it could be bundled with the weave python package.

See PR https://github.com/wandb/core/pull/8926 for details.

### FAQ

#### I am a frontend developer. How will the migration from app -> @wandb/weave affect my development workflow?

The only effect this refactor should have on your development is that it changes where you import certain objects from. Instead of doing

```typescript
import makeComp from '../util/profiler';
```

you would now do

```typescript
import makeComp from '@wandb/weave/common/util/profiler';
```

This change does _not:_

- Change any of the commands you use to build, lint, test, install, or deploy the application
- Add any additional devops steps to the local development workflow
- Add additional dependencies for you to manage
- Require you to perform any migrations
- Alter the functionality of the application

It only changes where certain code lives.

#### I have a new function, component, or object that I have written. Should I put it in `common/`?

Only put things into `common/` if they are also needed by `@wandb/weave`. If something you have written is not needed by `@wandb/weave`, just put it in `app/`.
