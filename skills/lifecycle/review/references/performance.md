# Performance checklist

Use the sections that match what the diff touches. Flag only issues with a real cost on a realistic input size, and say what that size is.

## Algorithms and data
- [ ] No nested loops over collections that can grow; use a lookup map or set instead.
- [ ] No repeated work inside loops: parsing, regex compilation, file reads or network calls.
- [ ] Large inputs are streamed or paged, not loaded whole into memory.
- [ ] Collections built in a loop avoid quadratic appends, such as `+=` on PowerShell arrays.

## Data access
- [ ] No N+1 pattern: one query or call per item where a batch or join would do.
- [ ] List queries are filtered, paginated and select only the fields needed.
- [ ] Filters and sorts hit indexed columns; new query shapes have a matching index.
- [ ] Connections and clients are reused, not created per call.

## Network and I/O
- [ ] Independent calls run concurrently where the platform allows it.
- [ ] Calls have timeouts and bounded retries with backoff.
- [ ] Results that rarely change are cached with a clear expiry.
- [ ] No blocking I/O on a request, UI or event-loop thread.

## Startup and hot paths
- [ ] Work on startup, logon, prompt or hook paths is minimal, and deferred or lazy where possible.
- [ ] No synchronous network or process calls on every invocation of a hook or command.
- [ ] Heavy modules are imported only where used.

## Frontend
- [ ] No extra re-renders from unstable props, inline objects or broad state subscriptions.
- [ ] Long lists are virtualised or paginated.
- [ ] Images are sized, compressed and lazy loaded below the fold.
- [ ] Bundle growth from new dependencies is justified; code splitting where it helps.
- [ ] No layout shift from late-loading content; interaction handlers stay short.

## Infrastructure
- [ ] SKUs, instance counts and autoscale limits match the expected load and cost.
- [ ] Resources that talk to each other are in the same region.
- [ ] Logging and telemetry volume is bounded and sampled where high.
