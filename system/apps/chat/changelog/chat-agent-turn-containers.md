Each agent turn now has its own container element in the page, and the navigation rail targets that.

Most of the agent's prose renders inside a collapsed step, where it has no element of its own, so a rail entry naming it had nothing to scroll to. Its turn is now wrapped in a container named after the same event the outline names the entry by, so there is always something in the page that stands for that reply. User entries are unaffected -- their message is a top-level row already, which is why they always worked.

Verified on a real conversation: every mounted container's id matches an outline entry, none unmatched, and clicking an entry whose turn is mounted lands it correctly (whole turn at the viewport bottom when it fits, its start at the top when it does not).

Still outstanding: an entry whose turn is not currently mounted does not navigate. Only a few turns are rendered at a time, and the jump does not reliably bring a distant one in. That is the remaining piece of this feature.
