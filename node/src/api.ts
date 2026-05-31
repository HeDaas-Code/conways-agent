/**
 * API client for communicating with Python Brain
 */

const API_BASE = process.env.PYTHON_API_URL || 'http://localhost:8000';

export interface DialogueRequest {
  message: string;
}

export interface DialogueResponse {
  response: string;
}

export interface StatusResponse {
  sleep_state: 'awake' | 'sleeping';
}

/**
 * Send a dialogue message to the Python Brain
 */
export async function sendDialogue(message: string): Promise<DialogueResponse> {
  const response = await fetch(`${API_BASE}/api/dialogue`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message } satisfies DialogueRequest),
  });

  if (!response.ok) {
    throw new Error(`Dialogue API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get the current agent status
 */
export async function getStatus(): Promise<StatusResponse> {
  const response = await fetch(`${API_BASE}/api/status`);

  if (!response.ok) {
    throw new Error(`Status API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
