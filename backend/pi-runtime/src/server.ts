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
    const sourceContext = params?.source_context || "";
    console.error(`[PI_TOOL] generate_ship30_essay called with topic: ${topic}, context length: ${sourceContext.length}`);
    // Return context for the Pi agent to synthesize into an essay
    return {
      content: [{ type: "text", text: sourceContext || `Context for essay on ${topic}` }],
      details: {
        status: "success",
        topic: topic,
        context_provided: !!sourceContext
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
    console.error(`[PI_TOOL] create_artifact called with type: ${artType}, title: ${title}, content length: ${content.length}`);
    // Return content for the Pi agent to process/save
    return {
      content: [{ type: "text", text: content }],
      details: {
        status: "created",
        type: artType,
        title: title,
        content_provided: !!content
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

CRITICAL RULE FOR create_artifact ONLY:
This brief-response rule applies ONLY when you call create_artifact.
After you successfully call create_artifact, your chat response MUST be brief and MUST NOT include the full artifact content in a fenced code block.
Instead, say something like: "I've created the [title] artifact — you can view and edit it in the panel on the right."
The full content is automatically rendered in the artifact panel separately. Do NOT duplicate it in the chat.

IMPORTANT: When you call generate_ship30_essay, your full essay text IS the chat response — stream it directly into the chat bubble. Do NOT summarize it or redirect to a panel. Essays are conversational content, not artifacts.

Rules:
- Strictly ground your answers in retrieved transcript content.
- Always cite the guest and episode when providing advice drawn from transcripts.
- If retrieval produces no relevant results, explicitly say so rather than guessing.

IMPORTANT: Users will not always say 'use the search tool' or 'generate an artifact' explicitly — recognize requests like 'what does X say about Y', 'write an essay on Z', or 'give me a report on W' as needing search_transcripts, generate_ship30_essay, or create_artifact respectively, even without those exact words.

For create_artifact specifically, recognize varied phrasings like:
- 'create an HTML artifact' or 'create a markdown artifact'
- 'HTML artifact' or 'markdown artifact' appearing anywhere in the message
- 'styled CSS', 'interactive page/tool/calculator'
- 'generate a document', 'write a guide', 'make me a report'

Ship30 Essay Requirements (when using generate_ship30_essay):
- Target word count: 1100-1400 words
- Start with a powerful hook (1-2 sentences that grab attention)
- Use bold subheadings for key sections
- Use bullet points for key insights
- End with a clear, actionable takeaway
- Keep it concise and skimmable
- Ground everything in the provided transcript context

Artifact Generation Requirements (when using create_artifact):
- CRITICAL: You MUST synthesize the retrieved transcript context into genuine, structured content BEFORE calling create_artifact.
- Do NOT pass raw retrieved context directly to create_artifact.
- Create well-structured, professional documents with clear headings and sections
- Make content actionable and practical
- Ground it in the provided transcript context
- If the user didn't specify a title, create a descriptive one based on the content`;

function send(msg: any) {
  process.stdout.write(JSON.stringify(msg) + "\n");
}

async function handleRequest(req: any) {
  const { id, session_id, messages, provider, model, api_key } = req;

  console.error(`[PI_RPC] Received model: ${JSON.stringify(model)}, provider: ${JSON.stringify(provider)}`);

  try {
    const llmProvider = provider || "openai";
    const llmModel = model || "gpt-4o-mini";

    console.error(`[PI_RPC] Using model: ${JSON.stringify(llmModel)} (source: ${model ? 'session.llm_model' : 'fallback default'})`);

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
