Two fixes to the chat navigation rail.

The highlight no longer lands on the wrong entry while scrolling. It was comparing message positions using `offsetTop`, which is measured from the nearest positioned ancestor rather than from the scroll container, so every comparison was off by the distance between the two. Positions are now measured in the scroller's own coordinates, as the click-to-scroll code already did.

Clicking one of the agent's entries now brings the whole reply into view rather than its first line. An entry points at the first speaking message of a reply, which is often a single line; landing that row alone left the actual reply below the fold. An entry now stands for its whole span -- from its own message down to wherever the next entry begins -- and the fits-at-the-bottom / starts-at-the-top rule is applied to that.
