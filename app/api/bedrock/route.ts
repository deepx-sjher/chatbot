// // app/api/bedrock/route.ts  (Node 런타임)
// import {
//   BedrockAgentRuntimeClient,
//   InvokeAgentCommand,
// } from "@aws-sdk/client-bedrock-agent-runtime";
// import { createDataStreamResponse } from "ai";

// export const runtime = "nodejs";   // Edge가 아니므로 ENV Credential 자동 인식
// export const maxDuration = 30;

// const client = new BedrockAgentRuntimeClient({
//   region: process.env.AWS_REGION!,
// });

// export async function POST(req: Request) {
//   const { messages, sessionId = crypto.randomUUID() } = await req.json();

//   const cmd = new InvokeAgentCommand({
//     agentId:      onlyId(process.env.BEDROCK_AGENT_ID!),
//     agentAliasId: onlyId(process.env.BEDROCK_AGENT_ALIAS_ID!),
//     sessionId,
//     inputText:    messages.at(-1)?.content ?? "",
//   });

//   const res = await client.send(cmd);   // ← 형식이 맞지 않으면 여기서 UnknownError

//   return createDataStreamResponse({
//     async execute(stream) {
//       for await (const ev of res.completion ?? []) {
//         if (ev.chunk?.bytes)
//           stream.write(new TextDecoder().decode(ev.chunk.bytes));
//       }
//     },
//   });
// }
