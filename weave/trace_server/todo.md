* Finish Porting over weave client
* [ ] Add end-to-end test with new lifecycle: 
  * Create Dummy Model via API -> See in object explorer
    * Requires finishing the leaf object registry
    * Requires sub process construction & saving?
  * Invoke Dummy Model via API -> See in trace explorer
    * Requires execution in sub process
  * Create a Dummy Scorer via API -> See in object explorer
    * Should be pretty straight forward at this point
  * Invoke the Scorer against the previous call via API -> see in traces AND in feedback
    * Should be mostly straight forward (the Scorer API itself is a bit wonky)
  * Important Proof of system: 
    * create the same dummy model locally & invoke -> notice no version change
    * Run locally against the call -> notice that there are no extra objects
* [ ] Refactor the entire "base model" system to conform to this new way of doing things (leaf models)
* [ ] Figure out how to refactor scorers that use LLMs
  * [ ] a new process with correct env setup (from secret fetcher?)
  * [ ] scorers should have a client-spec, not a specific client