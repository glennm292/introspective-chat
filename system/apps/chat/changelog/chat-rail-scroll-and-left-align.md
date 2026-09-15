Scrolling the chat is no longer fought by the navigation rail, and the chat body is left-aligned.

Any direct scroll input on the transcript -- wheel, touch, pointer, keys -- now cancels whatever programmatic scrolling the rail had in flight. A click on a rail entry starts a loop that keeps re-landing the message as the virtualized transcript shifts under it, and that loop previously ran for its full deadline regardless of what the user did, so the chat could refuse to move. The user is now always in charge.

The rail likewise stops following the transcript for a moment after the user scrolls the rail itself, so browsing the list does not get yanked back.

The outline also no longer refetches on every event of a live turn. Growth is coalesced into one refresh per window, and a refresh that finds nothing new no longer redraws the chat underneath it.

Separately, the message column, the activity strip and the composer are left-aligned rather than centered, and the composer is inset by the rail's width (one shared CSS variable) so it lines up with the messages above it.
