TODO:

- [ ] In Browse3/2 (folders and roots), we should always be using the router context for route calculation, audit all cases of:
  - [ ] `<Link` (to)
  - [ ] `history.` (push/replace)
  - Important: entity/project should never be directly constructed from orm
- [ ] Need to find all places where we have a version hash in filters (can look at filter type specs). These should all be a more fully-qualified URI (at least include entity/project). Should probably always use URI field (audit cases of `":"``)
- [ ] Defense: ORM construction should accept entity/project - this will force us to pass that through the component tree and allow us to ensure we have the correct orm
- [ ] Audit all ORMs(can lok for the hook) - entity/project should never be directly constructed from orm
- [ ] Move the "NewRouteProvider" -> probably want to call it something else, to the entrypoint
