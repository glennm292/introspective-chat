The Agent Overview's tokens are now a single row: Input, Cached, Output.

Two rows against three columns gave the grid a hole -- Output has no cached figure, because generated tokens are never served from a cache -- and spent two lines on three numbers. One row of three says the same thing without the gap.

Input still counts tokens written into the cache: the model read those for the first time as well as storing them, so they are new traffic rather than a saving. Cached is what came back out of it.
