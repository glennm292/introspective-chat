import { describe, it, expect } from "vitest";
import type { AssistantMessageEvent, ToolCall } from "../models/Response";
import { groupedWorkEventIds } from "./work-grouping";

function base(id: string): AssistantMessageEvent {
  return {
    timestamp: "t",
    type: "assistant_message",
    event_id: id,
    source: "test",
    model: "m",
    text: "",
    tool_calls: [],
    stop_reason: null,
    usage: null,
    is_auth_error: false,
    is_api_error: false,
    api_error_kind: null,
    is_provider_fault: false,
  };
}

function prose(id: string, text = "Doing the thing."): AssistantMessageEvent {
  return { ...base(id), text };
}

function work(id: string): AssistantMessageEvent {
  const toolCall: ToolCall = { tool_call_id: `${id}-c`, tool_name: "Bash", input_chars: 4 };
  return { ...base(id), tool_calls: [toolCall] };
}

describe("groupedWorkEventIds", () => {
  it("groups the work a sentence introduced", () => {
    const grouped = groupedWorkEventIds([prose("p1"), work("w1")]);
    expect([...grouped]).toEqual(["w1"]);
  });

  it("groups a whole batch under one sentence, not just the first call", () => {
    // The common shape: one sentence, then several messages of work.
    const grouped = groupedWorkEventIds([prose("p1"), work("w1"), work("w2"), work("w3")]);
    expect([...grouped]).toEqual(["w1", "w2", "w3"]);
  });

  it("leaves work with no sentence before it ungrouped", () => {
    // There is nothing to indent it under, and inventing a reason is exactly what
    // this must not do.
    const grouped = groupedWorkEventIds([work("w1"), work("w2")]);
    expect(grouped.size).toBe(0);
  });

  it("starts a new group at the next sentence", () => {
    const grouped = groupedWorkEventIds([prose("p1"), work("w1"), prose("p2"), work("w2")]);
    expect([...grouped]).toEqual(["w1", "w2"]);
  });

  it("never groups the sentences themselves", () => {
    // The sentence keeps its place in the flow; only the work below it is indented.
    const grouped = groupedWorkEventIds([prose("p1"), work("w1")]);
    expect(grouped.has("p1")).toBe(false);
  });

  it("ignores a message that is neither prose nor work", () => {
    const empty = prose("e1", "");
    const grouped = groupedWorkEventIds([prose("p1"), empty, work("w1")]);
    expect(grouped.has("w1")).toBe(true);
  });

  it("handles an empty run", () => {
    expect(groupedWorkEventIds([]).size).toBe(0);
  });
});
