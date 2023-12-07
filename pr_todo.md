Bugs:

- [ ] Do to static state, committing changes errors when attempting to load the new page.
- [ ] Add to Dataset is broken - might be due to weird imports in server
- [ ] Feedback does not save correctly

---

Shortcuts Taken

- Op & Type category are not formally part of the data model (and therefore are inferred from names)
- Specific Op and Type categories are hard-coded for now
- TypeVersions are not formally part of the data model (and therefore are constructed by reading all the data & manually calculating a hash/id).
- Only the `Calls` table is actually backed by a Weave query - the other tables are just pure data.
- Since OpDefs do not store their type stub, we have to infer it from the first call!
- Since OpDefs do not store their invoke list, we have to infer it from the first call!
- There is a not-well defined mapping between an in-memory WeaveType and it's corresponding virtual "TypeVersion"
- A lot of locations assume the same entity/project as the current one - probably need to audit this
- The filters are using `name:version` as the reference - should probably make this full path

Query & Performance:

- Naive ORM Implementation:
  - No support for live data
  - Recalculates every edge
  - Not Weave-based!
  - Requires loading the entire project into memory!

Future:

- Project Selector should limit to only "good" projects
- Project Homepage is a big opportunity for innovation (currently just redirects to calls)
- Selected Tab state not saved
- "Peak" style previews
- Ability to open any of the Table Pages in a board
- Structure and Record DAGS
- Board and Table Support (also in detail pages)
- Pinnable filters
- Odd Behavior: Only the main data view of objectversion adapts to nested URI
- FEAT: Show outputs when narrowed to a single op version
- FEAT: TypeVersion Filter (Include Subtypes)
- Ops Page: (Future)
- Types Page: (Future)
- Objects Page: (Future)
