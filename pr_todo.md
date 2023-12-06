PR Todos:

- Object Page

  - [ ] GAP: Not implemented

- Objects Page

  - [ ] GAP: Not implemented

- ObjectVersions Page

  - [ ] BUG: Filter controls seem to get "stuck", resulting in internal state mismatched with displayed state.
  - [ ] BUG: Clearing all filters results in no rows
  - [ ] FEAT: Enable Description Editing

- [ ] ObjectVersion Page

  - [ ] BUG: Only the main data view adapts to nested URI
  - [ ] BUG: When ops are in the data view (odd) - they have incorrect links
  - [ ] BUG: Committing edits redirects to incorrect page
  - [ ] FEAT: Board listing Page
  - [ ] FEAT: Record DAG
  - [ ] FEAT: TypeVersion Filter (Include Subtypes)
  - [ ] GAP: "Open in Board" opens in old link
  - [ ] GAP: `/versions` does not redirect
  - [ ] GAP: Overview - type category

- Type Page

  - [ ] GAP: Not implemented

- Types Page

  - [ ] GAP: Not implemented

- TypeVersion Page

  - [ ] GAP: Show Consuming Ops
  - [ ] GAP: Show Producing Ops
  - [ ] GAP: Structure DAG
  - [ ] GAP: Overview - type category
  - [ ] GAP: `/versions` does not redirect

- TypeVersions Page

  - [ ] GAP: Implement Filters: (Type Category, Type Name, Consumed By, Produced By, Child Of Type, Parent Of Type)
  - [ ] GAP: Navbar link still uses old filter
  - [ ] GAP: Columns: Type Category, Consumed By (count), produced by (count), Type Hierarchy, Child Types (count)
  - [ ] BUG: Fix Navbar - no special link

- Op Page

  - [ ] GAP: Not implemented

- Ops Page

  - [ ] GAP: Not implemented

- OpVersion Page

  - [ ] GAP: Structure DAG
  - [ ] GAP: Overview: (Type Stub, Op Category, isLatest)
  - [ ] GAP: Tabs (produced by and called by)
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

- Board Page

  - [ ] GAP: Persistence & Config Editor - there are a lot of gaps here in terms of functionality

- Boards Page

  - [ ] GAP: Actions probably don't work

- Table Page

  - [ ] BUG: Does not work

- Tables

  - [ ] BUG: Does not work

- Data Model

  - [ ] Make op op cat inherit from parent

- Python API

  - [ ] Need to update URLs

- General
  - [ ] Deprecate `weave-js/src/components/PagePanelComponents/Home/Browse2/url.ts`

Shortcuts

- [ ] Op & Type category are not formally part of the data model (and therefore are inferred from names)
- [ ] Specific Op and Type categories are hard-coded for now
- [ ] TypeVersions are not formally part of the data model (and therefore are constructed by reading all the data & manually calculating a hash/id).
- [ ] Only the `Calls` table is actually backed by a Weave query - the other tables are just pure data.
- [ ] Since OpDefs do not store their type stub, we have to infer it from the first call!
- [ ] Since OpDefs do not store their invoke list, we have to infer it from the first call!
- [ ] There is a not-well defined mapping between an in-memory WeaveType and it's corresponding virtual "TypeVersion"
- [ ] Pinnable filters

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
