#!/usr/bin/env node
/**
 * MCP HTTP Proxy (robust)
 *
 * Bridges stdio-based MCP clients (Gemini, Claude) to an HTTP JSON-RPC MCP
 * server. Ensures correct sequencing:
 * - Buffer outbound messages until initialize completes and session ID is set
 * - Auto-sends notifications/initialized if the client did not
 * - Adds Mcp-Session-Id to all subsequent requests
 *
 * Usage:
 *   node scripts/mcp-http-proxy.mjs <server-url> [auth-token]
 * Example:
 *   node scripts/mcp-http-proxy.mjs https://example.com/mcp/http my-token
 */

import readline from 'node:readline';

const SERVER_URL = process.argv[2];
const AUTH_TOKEN = process.argv[3] || null;

if (!SERVER_URL) {
  console.error('Usage: mcp-http-proxy.mjs <server-url> [auth-token]');
  process.exit(2);
}

const stdin = process.stdin;
const stdout = process.stdout;
const stderr = process.stderr;

/** Common headers for HTTP JSON-RPC requests */
const baseHeaders = {
  'Content-Type': 'application/json',
  Accept: 'application/json, text/event-stream',
};

/** Proxy state */
let sessionId = null; // string | null
let initializeCompleted = false;
let initializedNotified = false;
const bufferedMessages = []; // messages received before initialize completes
let processingMessage = false; // mutex to prevent concurrent processing
const messageQueue = []; // queue for serial processing
let stdinClosed = false; // track if stdin has closed

function buildHeaders() {
  const headers = { ...baseHeaders };
  if (AUTH_TOKEN) headers['Authorization'] = `Bearer ${AUTH_TOKEN}`;
  if (sessionId) headers['Mcp-Session-Id'] = sessionId;
  return headers;
}

async function sendJsonRpc(message) {
  // Send a single JSON-RPC message to the HTTP endpoint
  const headers = buildHeaders();
  const body = JSON.stringify(message);
  try {
    const resp = await fetch(SERVER_URL, {
      method: 'POST',
      headers,
      body,
    });

    // Capture session ID if provided by server
    const newSid = resp.headers.get('mcp-session-id');
    if (newSid) {
      sessionId = newSid;
      stderr.write(`<- Session ID: ${sessionId}\n`);
    }

    const text = await resp.text();

    if (!resp.ok) {
      // Don't send errors for auto-generated notifications or if stdin closed
      if (message.id && !stdinClosed) {
        const errorResponse = {
          jsonrpc: '2.0',
          id: message.id,
          error: {
            code: -32000,
            message: `HTTP error: ${resp.status}`,
            data: text,
          },
        };
        stdout.write(JSON.stringify(errorResponse) + '\n');
      }
      return;
    }

    if (!text || text.trim() === '') {
      // Notification ACK (202) or empty body
      return;
    }

    // Forward server response to client (only if stdin is still open)
    if (!stdinClosed) {
      stdout.write(text + '\n');
    }
  } catch (err) {
    // Only send errors for messages with IDs and if stdin is still open
    if (message.id && !stdinClosed) {
      const errorResponse = {
        jsonrpc: '2.0',
        id: message.id,
        error: {
          code: -32603,
          message: `Proxy error: ${err.message}`,
        },
      };
      stdout.write(JSON.stringify(errorResponse) + '\n');
    }
  }
}

async function handleAfterInitialize() {
  // If client has not notified initialized, proactively do so once
  if (!initializedNotified) {
    const notif = { jsonrpc: '2.0', method: 'notifications/initialized', params: {} };
    await sendJsonRpc(notif);
    initializedNotified = true;
  }

  // Flush buffered messages in original order
  while (bufferedMessages.length > 0) {
    const msg = bufferedMessages.shift();
    // Track if client explicitly notifies initialized
    if (msg.method === 'notifications/initialized') initializedNotified = true;
    await sendJsonRpc(msg);
  }
}

async function routeMessage(message) {
  // Maintain minimal sequencing guarantees around initialize
  if (message && message.method === 'initialize') {
    // Send initialize, await response to get sessionId
    await sendJsonRpc(message);
    initializeCompleted = true;
    await handleAfterInitialize();
    return;
  }

  if (!initializeCompleted) {
    // Buffer everything until initialize completes
    bufferedMessages.push(message);
    return;
  }

  // Track explicit initialized notification
  if (message.method === 'notifications/initialized') initializedNotified = true;

  // Ensure server is notified about initialized exactly once before other calls
  if (!initializedNotified && message.method !== 'notifications/initialized') {
    await sendJsonRpc({
      jsonrpc: '2.0',
      method: 'notifications/initialized',
      params: {},
    });
    initializedNotified = true;
  }

  await sendJsonRpc(message);
}

function safeParse(line) {
  try {
    return JSON.parse(line);
  } catch (e) {
    // Ignore malformed lines; emit error back to client
    const errorResponse = {
      jsonrpc: '2.0',
      id: 'server-error',
      error: { code: -32700, message: 'Parse error' },
    };
    stdout.write(JSON.stringify(errorResponse) + '\n');
    return null;
  }
}

// Serial message processor to avoid race conditions
async function processNextMessage() {
  if (processingMessage || messageQueue.length === 0) return;
  
  processingMessage = true;
  const message = messageQueue.shift();
  
  try {
    await routeMessage(message);
  } catch (err) {
    stderr.write(`Error processing message: ${err.message}\n`);
  } finally {
    processingMessage = false;
    // Process next message if any
    if (messageQueue.length > 0) {
      setImmediate(processNextMessage);
    }
  }
}

// Read JSON-RPC messages line-by-line from stdin
const rl = readline.createInterface({ input: stdin, crlfDelay: Infinity });

stderr.write('MCP HTTP Proxy (robust) starting...\n');
stderr.write(`Server: ${SERVER_URL}\n`);
stderr.write(`Auth: ${AUTH_TOKEN ? 'Enabled' : 'Disabled'}\n\n`);

rl.on('line', (line) => {
  if (!line || !line.trim()) return;
  const message = safeParse(line);
  if (!message) return;

  // Echo intent for debugging
  stderr.write(`-> Queued: ${message.method ?? 'unknown'} (id: ${String(message.id)})\n`);

  // Add to queue and process serially
  messageQueue.push(message);
  processNextMessage();
});

rl.on('close', () => {
  stdinClosed = true;
  stderr.write('MCP HTTP Proxy shutting down\n');
});


