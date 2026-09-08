/*
Add `sentiment_target` to `intent_signatures`, the same way `sentiment_rationale`
was added: a judge-emitted field distinguishing who negative sentiment is
directed at (agent, product, own_work, unclear), stored so it can be filtered
and queried independently of the sentiment label itself.
*/
ALTER TABLE intent_signatures
    ADD COLUMN IF NOT EXISTS sentiment_target LowCardinality(String) DEFAULT 'unclear';
