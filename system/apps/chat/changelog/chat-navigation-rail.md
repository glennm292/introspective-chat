A navigation rail down the left of the chat lists every message in the conversation.

Each entry shows the opening of a message -- yours or the agent's -- clamped to two lines, so a short message appears whole and a long one is recognisable by how it starts. Nothing is generated or summarised: the rail shows text the conversation already contains. Entries lean the way their message sits in the transcript, the agent's flush left and yours inset and tinted.

The list covers the WHOLE conversation, not the part currently loaded. A new `/api/agents/<id>/outline` endpoint walks every event once and returns just the openings; this session's 968 events reduce to 28 entries in 6.4 KB. Without it the rail would gain and lose entries while scrolling, since the transcript only holds a window at a time.

The highlight follows the transcript as it scrolls, marking the newest message any part of which is on screen, and the rail scrolls itself to keep that entry in view. Clicking an entry scrolls its message into place: the whole message at the bottom of the viewport when it fits, its start at the top when it does not.

Known gap: clicking an entry whose message is outside the currently loaded window does not navigate yet. See the note in `TranscriptOutline.goToEntry` -- the fill planner already supports focusing an event index; the scroll engine just does not expose a way to set it.

Separately, a tool call's header now sets its verb in the reading face at full contrast and keeps the monospace, quieter type for the command or path alone, so the two halves read as prose and machine text rather than one undifferentiated string.
