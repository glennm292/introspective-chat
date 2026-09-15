Fixed a transcript geometry bug introduced by the agent-turn containers.

The scroll engine caches each row's measured height under the DOM id of the row's rendered root, and reads it back by row key -- so the root's id must BE the row key. Wrapping agent turns in a container made the wrapper the root, carrying a different id, so every progress block's real height was stored under a key no row used and each block kept its crude 360px estimate instead. The transcript's total height was wrong by about 3,800px on a real conversation, which makes any scroll position derived from that geometry wrong too.

The wrapper now carries the row key and the turn container id moves to the block inside it, so the rail still has its target and the engine measures correctly again.
