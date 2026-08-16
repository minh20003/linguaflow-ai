#!/usr/bin/env node

import { appendFileSync, existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
const valueFor = (flag) => {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : undefined;
};

function git(...gitArgs) {
  const result = spawnSync("git", gitArgs, { encoding: "utf8" });
  return result.status === 0 ? result.stdout.trim() : "";
}

function repoRoot() { return git("rev-parse", "--show-toplevel") || process.cwd(); }
function logPath(root) {
  const folder = join(root, ".ai-log");
  mkdirSync(folder, { recursive: true });
  return join(folder, "session.jsonl");
}
function append(root, record) { appendFileSync(logPath(root), `${JSON.stringify(record)}\n`, "utf8"); }
function metadata(root) {
  return {
    project: root.split(/[\\/]/).pop(), repo: git("config", "--get", "remote.origin.url"),
    branch: git("branch", "--show-current"), commit: git("rev-parse", "HEAD"),
    user_email: git("config", "user.email")
  };
}
function getUserText(item) {
  if (item?.type !== "response_item" || item?.payload?.type !== "message" || item.payload.role !== "user") return "";
  return (item.payload.content || []).filter((part) => part?.type === "input_text" && typeof part.text === "string").map((part) => part.text).join("\n");
}
function backfill(transcript) {
  const absolute = resolve(transcript);
  if (!existsSync(absolute)) throw new Error(`Không tìm thấy transcript: ${absolute}`);
  const parsed = readFileSync(absolute, "utf8").split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  const session = parsed.find((item) => item.type === "session_meta")?.payload?.id || "";
  const root = repoRoot();
  const logFiles = [logPath(root)];
  const archiveDir = join(root, ".ai-log", "archive");
  if (existsSync(archiveDir)) {
    logFiles.push(...readdirSync(archiveDir).filter((file) => file.endsWith(".jsonl")).map((file) => join(archiveDir, file)));
  }
  const loggedMessageIds = new Set();
  for (const file of logFiles) {
    if (!existsSync(file)) continue;
    for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
      try {
        const record = JSON.parse(line);
        if (record.source_message_id) loggedMessageIds.add(record.source_message_id);
      } catch { /* Ignore incomplete or legacy records. */ }
    }
  }
  let added = 0;
  for (const item of parsed) {
    const prompt = getUserText(item);
    const messageId = item?.payload?.id || item?.id || "";
    if (!prompt || !messageId || loggedMessageIds.has(messageId)) continue;
    append(root, { timestamp: item.timestamp || new Date().toISOString(), tool: "codex", event: "TranscriptBackfill", session_id: session, source_message_id: messageId, prompt, transcript_path: absolute, ...metadata(root) });
    added += 1;
    loggedMessageIds.add(messageId);
  }
  console.log(`Đã bổ sung ${added} prompt từ transcript Codex vào .ai-log/session.jsonl.`);
}

try {
  const transcript = valueFor("--backfill");
  if (transcript) backfill(transcript);
  else {
    const input = readFileSync(0, "utf8").trim();
    if (input) {
      const root = repoRoot();
      const event = JSON.parse(input);
      append(root, { timestamp: new Date().toISOString(), tool: valueFor("--tool") || "codex", event: event.hook_event_name || "Unknown", session_id: event.session_id || "", turn_id: event.turn_id || "", prompt: event.prompt || "", transcript_path: event.transcript_path || "", cwd: event.cwd || process.cwd(), ...metadata(root) });
    }
  }
} catch (error) {
  console.error(`[codex-log] ${error.message}`);
  process.exit(0);
}
