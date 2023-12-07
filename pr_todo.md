Pages:

- Object Page: Done
- ObjectVersions Page
- ObjectVersion Page: Done
- Type Page: Done
- TypeVersion Page Done
- TypeVersions Page: Done
- Op Page: Done
- OpVersion Page: Done
- OpVersions Page: Done
- Call Page: Done
- Calls Page: Done

Python API

- [ ] Need to update URLs

Bugs:

- [ ] Do to static state, committing changes errors when attempting to load the new page.
- [ ] Add to Dataset is broken - might be due to weird imports in server
- [ ] Feedback does not save correctly

Needs Cleanup:

- [ ] Use of version hashes in filter - need to convert everything to uris
- [ ] Various locations use context to get entity/project - this is bad as it assumes all links are within the same project

---

Shortcuts Taken

- Op & Type category are not formally part of the data model (and therefore are inferred from names)
- Specific Op and Type categories are hard-coded for now
- TypeVersions are not formally part of the data model (and therefore are constructed by reading all the data & manually calculating a hash/id).
- Only the `Calls` table is actually backed by a Weave query - the other tables are just pure data.
- Since OpDefs do not store their type stub, we have to infer it from the first call!
- Since OpDefs do not store their invoke list, we have to infer it from the first call!
- There is a not-well defined mapping between an in-memory WeaveType and it's corresponding virtual "TypeVersion"

Query & Performance:

- Naive ORM Implementation:
  - No support for live data
  - Recalculates every edge
  - Not Weave-based!
  - Requires loading the entire project into memory!

Future:

- Project Selector should limit to only "good" projects
- Project Homepage is a big opportunity for innovation
- Tab state not saved
- "Peak" style previews
- Ability to open any of the Table Pages in a board
- Structure and Record DAGS
- Board and Table Support
- Pinnable filters
- Odd Behavior: Only the main data view adapts to nested URI
- (Future) FEAT: ObjectVersion Board listing Page
- (Future) GAP: ObjectVersion "Open in Board" opens in old link
- FEAT: Show outputs when narrowed to a single op version
- FEAT: TypeVersion Filter (Include Subtypes)
- Ops Page: (Future)
- Types Page: (Future)
- Objects Page: (Future)
- Board Page: (Future)
- Boards Page: (Future)
- Table Page: (Future)
- Tables: (Future)
