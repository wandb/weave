PR Todos:

- Object Page: Done
- Objects Page: (Future)
- ObjectVersions Page

  - [ ] BUG: Filter controls seem to get "stuck", resulting in internal state mismatched with displayed state.
  - [ ] BUG: Clearing all filters results in no rows
  - [ ] FEAT: Enable Description Editing
  - [ ] FEAT: TypeVersion Filter (Include Subtypes)

- [ ] ObjectVersion Page

  - [ ] BUG: Only the main data view adapts to nested URI
  - [ ] BUG: When ops are in the data view (odd) - they have incorrect links
  - [ ] BUG: Committing edits redirects to incorrect page
  - [ ] (Future) FEAT: Board listing Page
  - [ ] (Future) FEAT: Record DAG
  - [ ] (Future) GAP: "Open in Board" opens in old link
  - [ ] GAP: `/versions` does not redirect

- Type Page: Done
- Types Page: (Future)
- TypeVersion Page

  - [ ] GAP: Overview - type category
  - [ ] GAP: `/versions` does not redirect

- TypeVersions Page: Done
- Op Page: Done
- Ops Page: (Future)
- OpVersion Page

  - [ ] GAP: Overview: (Type Stub, Op Category, isLatest, Call Hierarchy)
  - [ ] GAP: `/versions` does not redirect

- OpVersions Page

  - [ ] GAP: Implement Filters: (Op Category, Latest, Op Name, Calls, Called By, Consumes Type (count), Produces Type)
  - [ ] GAP: Columns: Op Category, Op Name, Calls, Called By, Consumes Type, Produces Type
  - [ ] FEAT: Enable Description Editing
  - [ ] BUG: Fix Navbar to do proper linking

- Call Page

  - CHECK: Add "TODO" to overflow menu
  - CHECK: Add to dataset? What does this do now?
  - CHECK: Feedback
  - [ ] FEAT: Add op Category
  - [ ] BUG: Function link is broken (possibly same as other issues above)

- Calls Page

  - [ ] FEAT: Show outputs when narrowed to a single op version

- Board Page: (Future)
- Boards Page: (Future)
- Table Page: (Future)
- Tables: (Future)
- Python API

  - [ ] Need to update URLs

- General
  - [ ] Deprecate `weave-js/src/components/PagePanelComponents/Home/Browse2/url.ts`
  - [ ] No tables save their filter state back to the URL

Shortcuts Taken

- Op & Type category are not formally part of the data model (and therefore are inferred from names)
- Specific Op and Type categories are hard-coded for now
- TypeVersions are not formally part of the data model (and therefore are constructed by reading all the data & manually calculating a hash/id).
- Only the `Calls` table is actually backed by a Weave query - the other tables are just pure data.
- Since OpDefs do not store their type stub, we have to infer it from the first call!
- Since OpDefs do not store their invoke list, we have to infer it from the first call!
- There is a not-well defined mapping between an in-memory WeaveType and it's corresponding virtual "TypeVersion"

Query & Performance:

- [ ] Naive ORM Implementation:
  - [ ] No support for live data
  - [ ] Recalculates every edge
  - [ ] Not Weave-based!
  - [ ] Requires loading the entire project into memory!

Future:

- [ ] Project Selector should limit to only "good" projects
- [ ] Project Homepage is a big opportunity for innovation
- [ ] Tab state not saved
- [ ] "Peak" style previews
- [ ] Ability to open any of the Table Pages in a board
- [ ] Structure and Record DAGS
- [ ] Board and Table Support
- [ ] Pinnable filters

Needs Cleanup:

- [ ] Use of version hashes in filter - need to convert everything to uris
- [ ] Various locations use context to get entity/project - this is bad as it assumes all links are within the same project
