Clicking any entry in the navigation rail now scrolls to that message.

The jump was writing the correct scroll position and then being undone one frame later. The engine re-derives the scroll position from a stored anchor on each render, and the jump was storing that anchor BEFORE moving -- so the anchor described where the viewport had come from, and the engine dutifully put it back. The anchor is now recorded after the move, describing the destination.

Verified by clicking all 40 entries of a real conversation: every one resolves to its message, brings it on screen, and leaves the rail highlighting the entry that was clicked. Tall turns start at the top of the viewport, turns that fit end at the bottom, and the first messages of a conversation land as close to that as the top of the transcript allows.

Worth recording for anyone reading this code later: the conversation was fully loaded the whole time (1422 of 1422 events resident). The earlier theories about windowing and fetching were wrong; the engine's own scroll trace showed the revert in two lines.
