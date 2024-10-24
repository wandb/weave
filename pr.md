# PR TODOs

- [ ] Decide on the feedback schema that is appropriate for actions. There are concepts that seem to overlap (ex. config ~ self, score ~ action, etc...)
- [ ] Firm up the Action Spec (seems pretty good IMO)
- [ ] Python API for creating objects is pretty bad - especially when we want to reference other objects... this is not clean right now.
- [ ] Create the concept of a filter action (needs to have "enabled" attribute)
- [ ] UI Elements
   - [ ] Configured Actions
      - [ ] List
      - [ ] Create
      - [ ] Edit
      - [ ] Delete (delete objects)
      - [ ] View?
         - [ ] See Mappings
   - [ ] Mappings
      - [ ] List
      - [ ] Create
      - [ ] Edit
      - [ ] Delete (delete objects)
      - [ ] View?
         - [ ] Link to configured action
         - [ ] See Actioned Calls (listing of feedback)
   - [ ] Filter Action
      - [ ] List
      - [ ] Create
      - [ ] Edit
         - [ ] Disable / Pause
      - [ ] Delete (delete objects)
      - [ ] View?
         - [ ] Link to mapping
         - [ ] See "live feed" of applicable calls
    - [ ] Call Table
        - [ ] Action Result Column(s)
        - [ ] "Fill" Button (or create filter action - basically a single or live version)
    - [ ] Call View
        - [ ] Action Results
        - [ ] Single Execution Button (would be nice to have smart mapping)
   - [ ] OpVersion View
        - [ ] View associated mappings
- [ ] Create additional 


Decisions:
1. Use a standard name -> Pydantic Type for Objects and Feedback.
2. Action spec is pretty solid for now
3. Tomorrow:
   - [ ] UI for browsing/creating actions
   - [ ] UI for executing action first time with no action

----

