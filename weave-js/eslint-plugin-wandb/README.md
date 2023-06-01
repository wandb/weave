# Custom eslint rules

Sometimes we need some custom linting rules to protect us from breaking things.  If you want to add a new rule or extend the current rule you can link this in your dev environment to pickup changes during development.

```shell
cd plugins/eslint-plugin-wandb
yarn link
cd ../../
yarn link eslint-plugin-wandb
```

When developing rules I found it very useful to use the [AST Explorer](https://astexplorer.net/).  If you do make changes be sure to bump the version number in `package.json` so that it will be upgraded in everyones dev environment when `yarn install` is run.

## No A Tags

This rule is intended to prevent the use of `<a` tags that link directly to other pages in our app.  Regular links will force the entire application to reload which makes for a bad user experience.  We also support users mounting our application under a path, i.e. https://internal.company.com/wandb.  React Router allows us to specify the base_path for all routes so using a `<Link` tag solves both of these problems.  There are cases where we want to link to fully qualified domains as well as external urls, here are some examples

```js
import {Link} from "react-router-dom"
import {TargetBlank} from "utils/links"
<a href="/some/url">  # 🙁 Bad
<Link to="/some/url">  # 🙂 Good
<TargetBlank href="https://some.com/url" /> # 🙂 Good
<a href="https://some.com/url" download="output.log"> # 🙂 Good
<a href="#" onClick={() => {}}> # 😐 Ok, <button> is preferred
```

We do allow `<a` tags for the following cases:

1. `<a href="..." target="_blank">` - Be aware however that you'll need to use `config.rootUrl()` if href is a link to our application.
2. `<a href="#">` - This is generally an anti-pattern and a `<button>` should likely be used, but we allow it.
3. `<a href="https://...">` - Links to external websites are allowed, but they would usually have a `target` so should be caught by #1.
4. `<a href="https://..." download="filename.txt"> - Links to download files can use the download attribute to bypass this rule.

If you do find a case where an a tag is appropriate, simply disable this rule with `<a href="..."></a> // eslint-disable-line wandb/no-a-tags`

## No Unprefixed Urls

This rule is intended to prevent redirecting the users browser to pages without accounting for the root path a wandb server could be running on.  We currently check for `window.open(...)` `window.location.href = ...`, `document.location.href = ...`, and `fetch(...)`.  As long as `urlPrefixed` from `config.ts` is being used we won't flag the error.

```js
window.location.href = "/foo" # 🙁 Bad
window.location.href = urlPrefixed("/foo") # 🙂 Good
fetch("/admin") # 🙁 Bad
fetch(urlPrefixed("/admin")) # 🙂 Good
```

We allow urls without a prefix in the following cases:

1. `window.open("https://docs.wandb.com")` - If we detect a literal that starts with http or `/site` we let it through
2. `window.location.href = file.directUrl` - If we detect `directUrl`, `ref`, or `uploadUrl` we allow them as these are going directly to cloud storage

If you know what you're doing and need to make an exception, simple disable this rule with `// eslint-disable-line wandb/no-unprefixed-urls`