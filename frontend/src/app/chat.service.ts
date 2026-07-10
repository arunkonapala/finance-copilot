import { Injectable } from '@angular/core';

export interface StreamEvent {
  type: 'session' | 'delta' | 'tool' | 'thinking' | 'done' | 'error';
  text?: string;
  name?: string;
  label?: string;
  message?: string;
  session_id?: string;
}

export interface Summary {
  net_worth: number;
  spent_this_month: number;
  bills_due_soon: number;
  next_bill: { name: string; amount: number; next_due_date: string } | null;
  accounts: { name: string; type: string; balance: number }[];
}

// Same-origin in production (backend serves the built frontend);
// localhost:8000 only when running `ng serve` against a local backend.
const API = location.port === '4200' ? 'http://localhost:8000' : '';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private sessionId: string | null = null;

  /** POST the message and yield SSE events as they stream back. */
  async *send(message: string): AsyncGenerator<StreamEvent> {
    const res = await fetch(`${API}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: this.sessionId, message }),
    });
    if (!res.ok || !res.body) {
      throw new Error(`Backend returned ${res.status}.`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';
      for (const frame of frames) {
        const line = frame.trim();
        if (!line.startsWith('data:')) continue;
        const event = JSON.parse(line.slice(5)) as StreamEvent;
        if (event.type === 'session') {
          this.sessionId = event.session_id ?? null;
        } else {
          yield event;
        }
      }
    }
  }

  async summary(): Promise<Summary> {
    const res = await fetch(`${API}/api/summary`);
    if (!res.ok) throw new Error(`Backend returned ${res.status}`);
    return res.json();
  }
}
