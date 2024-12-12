* [x] Finish Porting over weave client
* [ ] Add end-to-end test with new lifecycle: 
  * [x] Create Dummy Model via API -> See in object explorer
    * [x] Requires finishing the leaf object registry
    * [x] Requires sub process construction & saving?
  * [x] Invoke Dummy Model via API -> See in trace explorer
    * [x] Requires execution in sub process
  * New TODOs:
    * API Keys are not correctly setup in the sub runner
    * A bunch of naming issues all around (leaf, saver, etc...)
    * Not very good error handling
    * Server seems to get stuck when it crashes
    * Accidentally checked in parallelization disabling
  * Create a Dummy Scorer via API -> See in object explorer
    * [x] Should be pretty straight forward at this point
  * Invoke the Scorer against the previous call via API -> see in traces AND in feedback
    * [x] Should be mostly straight forward (the Scorer API itself is a bit wonky)
  * Important Proof of system: 
    * [x] create the same dummy model locally & invoke -> notice no version change
    * [x] Run locally against the call -> notice that there are no extra objects
  * [ ]Should de-ref inputs if they contain refs
* [ ] Refactor the entire "base model" system to conform to this new way of doing things (leaf models)
  * [ ] Might get hairy with nested refs - consider implications
* [ ] Figure out how to refactor scorers that use LLMs
  * [ ] a new process with correct env setup (from secret fetcher?)
  * [ ] scorers should have a client-spec, not a specific client
  * [ ] How to model a scorers's stub (input, output, context, reference(s), etc...)
  * [ ] How to handle output types from scorers (boolean, number, reason, etc...)
  * [ ]Investigate why the tests are running so slowly


---- Decomposition PRs ----
1. Change/Add the set_object_class instead of base_object_class
2. Add new methods to the server