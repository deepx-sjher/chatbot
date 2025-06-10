import { openai } from "@ai-sdk/openai";
import { frontendTools } from "@assistant-ui/react-ai-sdk";
import { streamText } from "ai";

export const runtime = "nodejs";
export const maxDuration = 30;

export async function POST(req: Request) {
  console.log("λ OPENAI_API_KEY:", process.env.OPENAI_API_KEY?.slice(0, 5));
  const { messages, system, tools } = await req.json();

  const result = streamText({
    model: openai("gpt-4o"),
    messages,
    // forward system prompt and tools from the frontend
    toolCallStreaming: true,
    system,
    tools: {
      ...frontendTools(tools),
    },
    onError: console.log,
  });

  return result.toDataStreamResponse();
}
