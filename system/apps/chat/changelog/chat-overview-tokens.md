The Agent Overview now shows tokens.

A "Tokens out" column reports what the model generated. Tool kinds show a dash rather than a zero, because a tool call uses no tokens of its own -- its output becomes input to whichever model call reads it next, and is counted there. A line under the table says so, and gives the rest of the picture: fresh input tokens, tokens served from cache, and tokens written into it.

The column shows generated tokens alone rather than one combined figure, because the two halves differ by orders of magnitude -- on this conversation, 822k generated against 481M read from cache -- and a single "tokens" number would read as either trivial or alarming depending on which half you assumed it meant.

A call whose harness reports no usage, partial usage, or a malformed value contributes what it has and never a guess.
