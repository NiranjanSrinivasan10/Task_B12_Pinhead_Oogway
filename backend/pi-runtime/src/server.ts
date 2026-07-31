import * as readline from "readline";
import * as path from "path";
import * as fs from "fs";
import {
  getModel,
  registerApiProvider,
  Type,
  UserMessage,
  AssistantMessage,
  Message
} from "@mariozechner/pi-ai";
import { Agent, AgentTool, AgentEvent } from "@mariozechner/pi-agent-core";

// Load custom models.json if present
const modelsJsonPath = path.join(process.cwd(), "models.json");
if (fs.existsSync(modelsJsonPath)) {
  try {
    const raw = fs.readFileSync(modelsJsonPath, "utf-8");
    const parsed = JSON.parse(raw);
    if (parsed.providers) {
      for (const [name, config] of Object.entries<any>(parsed.providers)) {
        registerApiProvider(config, name);
      }
    }
  } catch (err) {
    console.error("Failed to load models.json:", err);
  }
}

// 1. search_transcripts tool stub
const searchTranscriptsTool: AgentTool = {
  name: "search_transcripts",
  label: "Search Transcripts",
  description: "Search Lenny's Podcast transcripts for relevant passages based on a query topic or keyword.",
  parameters: Type.Object({
    query: Type.String({ description: "The search query or topic keywords" })
  }),
  execute: async (toolCallId: string, params: any) => {
    const query = params?.query || "";
    return {
      content: [{ type: "text", text: "Stub transcript context for search: " + query }],
      details: {
        status: "success",
        query: query,
        results: [
          {
            episode_guest: "Brian Chesky",
            episode_title: "Brian Chesky’s new playbook",
            chunk_id: "stub-chunk-1",
            content: "Stub transcript context for search: " + query
          }
        ]
      }
    };
  }
};

// 2. generate_ship30_essay tool stub
const generateShip30EssayTool: AgentTool = {
  name: "generate_ship30_essay",
  label: "Generate Ship30 Essay",
  description: "Reformat knowledge or source context into a Ship30for30-style essay (~1250 words, strong hook, bulleted/bolded, clear takeaway).",
  parameters: Type.Object({
    topic: Type.String({ description: "Topic of the essay" }),
    source_context: Type.Optional(Type.String({ description: "Source context or ideas to reformat" }))
  }),
  execute: async (toolCallId: string, params: any) => {
    const topic = params?.topic || "Product Strategy";
    return {
      content: [{ type: "text", text: `Generated Ship30 essay on ${topic}` }],
      details: {
        status: "success",
        essay: `# ${topic}\n\n**Hook:** Here is a powerful takeaway.\n\n- Key insight 1\n- Key insight 2\n\n*Closing takeaway:* Apply this today.`
      }
    };
  }
};

// 3. create_artifact tool stub
const createArtifactTool: AgentTool = {
  name: "create_artifact",
  label: "Create Artifact",
  description: "Create and persist a rendered artifact (markdown or html UI snippet) for side-by-side display.",
  parameters: Type.Object({
    type: Type.String({ description: "Type of artifact ('markdown' or 'html')" }),
    title: Type.String({ description: "Title of the artifact" }),
    content: Type.String({ description: "Full content (markdown or HTML)" })
  }),
  execute: async (toolCallId: string, params: any) => {
    const artType = params?.type || "markdown";
    const title = params?.title || "Artifact";
    const content = params?.content || "";
    return {
      content: [{ type: "text", text: `Created ${artType} artifact: ${title}` }],
      details: {
        status: "created",
        artifact_id: "stub-artifact-1",
        type: artType,
        title: title,
        content: content
      }
    };
  }
};

// Grounding System Prompt
const SYSTEM_PROMPT = `You are The Lenny Growth Assistant, a full-stack RAG chatbot grounded strictly in Lenny's Podcast transcripts.
You have access ONLY to three custom tools:
1. search_transcripts — search episode transcripts for tactical advice
2. generate_ship30_essay — generate skimmable Ship30for30 essays
3. create_artifact — render markdown or HTML artifacts live in the UI

Rules:
- Strictly ground your answers in retrieved transcript content.
- Always cite the guest and episode when providing advice drawn from transcripts.
- If retrieval produces no relevant results, explicitly say so rather than guessing.`;

function send(msg: any) {
  process.stdout.write(JSON.stringify(msg) + "\n");
}

async function handleRequest(req: any) {
  const { id, session_id, messages, provider, model, api_key } = req;

  try {
    const llmProvider = provider || "openai";
    const llmModel = model || "gpt-4o-mini";

    if (api_key) {
      if (llmProvider === "openai") process.env.OPENAI_API_KEY = api_key;
      if (llmProvider === "anthropic") process.env.ANTHROPIC_API_KEY = api_key;
    }

    const modelInstance = getModel(llmProvider as any, llmModel as any);

    const agent = new Agent({
      initialState: {
        systemPrompt: SYSTEM_PROMPT,
        model: modelInstance,
        tools: [searchTranscriptsTool, generateShip30EssayTool, createArtifactTool]
      }
    });

    let lastSkillUsed: string | null = null;

    agent.subscribe((event: AgentEvent) => {
      if (event.type === "tool_execution_start") {
        lastSkillUsed = event.toolName;
        send({ id, type: "tool_call", tool: event.toolName, args: event.args });
      } else if (event.type === "tool_execution_end") {
        send({ id, type: "tool_result", tool: event.toolName, result: event.result });
      } else if (event.type === "message_update") {
        if (event.assistantMessageEvent.type === "text_delta") {
          send({ id, type: "token", content: event.assistantMessageEvent.delta });
        }
      }
    });

    const formattedMessages: Message[] = (messages || []).map((m: any) => {
      if (m.role === "user") {
        const userMsg: UserMessage = {
          role: "user",
          content: m.content,
          timestamp: Date.now()
        };
        return userMsg;
      } else {
        const assistantMsg: AssistantMessage = {
          role: "assistant",
          content: [{ type: "text", text: m.content }],
          api: modelInstance.api,
          provider: modelInstance.provider,
          model: modelInstance.id,
          usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
          stopReason: "stop",
          timestamp: Date.now()
        };
        return assistantMsg;
      }
    });

    await agent.prompt(formattedMessages);

    const history = agent.state.messages;
    let finalContent = "";
    for (let i = history.length - 1; i >= 0; i--) {
      const msg = history[i];
      if (msg.role === "assistant" && Array.isArray(msg.content)) {
        const textParts = msg.content
          .filter((c): c is { type: "text"; text: string } => c.type === "text")
          .map((c) => c.text);
        if (textParts.length > 0) {
          finalContent = textParts.join("\n");
          break;
        }
      }
    }

    send({
      id,
      type: "done",
      content: finalContent,
      skill_used: lastSkillUsed,
      retrieved_chunk_ids: []
    });
  } catch (err: any) {
    send({
      id,
      type: "error",
      error: err?.message || String(err)
    });
  }
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

rl.on("line", (line: string) => {
  const trimmed = line.trim();
  if (!trimmed) return;
  try {
    const req = JSON.parse(trimmed);
    handleRequest(req);
  } catch (err: any) {
    send({ id: null, type: "error", error: "Invalid JSON request: " + err.message });
  }
});

send({ type: "ready", status: "Pi RPC server running" });
