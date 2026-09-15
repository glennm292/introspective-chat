The conversation index now runs the full height of the chat pane, and the text input and bottom row of widgets sit beneath the message flow beside it.

The pane is now a row: the index down the left at full height, and a column to its right holding the transcript, the composer and the under-bar. The index sits outside the flip card for the same reason the under-bar does -- it describes the conversation rather than either rendering of it, so it must not rotate away when the terminal view is turned over.

This also retires the inset the composer needed while it spanned the whole pane width: it now lines up with the messages structurally rather than by matching a padding to the index's width.
