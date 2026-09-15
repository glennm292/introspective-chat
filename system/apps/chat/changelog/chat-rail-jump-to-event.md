The navigation rail no longer scrolls to the wrong message when the one you clicked is not on screen.

Clicking an entry used to fall back to scrolling the transcript proportionally, which landed on whatever message happened to be nearby and then moved the highlight to it -- so the rail appeared to jump to a different entry than the one clicked. That fallback is gone.

In its place the scroll engine gained `jumpToEventIndex`, a first-class way to put the viewport on a given message: it loads that region when the message is not resident (the same machinery a scrollbar drag into unloaded history uses), and moves to the message's own position when it is resident but not currently rendered.

Known limitation, unchanged by this: an entry whose message renders inside a COLLAPSED step block still cannot be scrolled to, because that message has no element in the page until the step is expanded. Most of the agent's prose is in that position, so most agent entries do not navigate. Making them work means the rail targeting (and likely expanding) the step that contains the message, rather than the message itself.
