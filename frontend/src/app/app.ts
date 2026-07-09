import { Component, ElementRef, OnInit, ViewChild, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService, Summary } from './chat.service';
import { MarkdownPipe } from './markdown.pipe';

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  tools: string[];
  error?: boolean;
}

@Component({
  selector: 'app-root',
  imports: [FormsModule, DecimalPipe, MarkdownPipe],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  @ViewChild('scroller') scroller?: ElementRef<HTMLElement>;

  messages = signal<ChatMessage[]>([]);
  draft = '';
  busy = signal(false);
  status = signal<string | null>(null);
  summary = signal<Summary | null>(null);

  readonly suggestions = [
    'Explain my latest statement to me',
    'Analyze my spending patterns — where does my money go?',
    'How am I tracking against my budget this month?',
    'Where could I realistically save more each month?',
    'What bills are due soon? Remind me 3 days before my car insurance.',
    'How is my portfolio performing?',
    "Explain index funds like I'm brand new to investing",
    'Build me a personalized financial plan',
  ];

  constructor(private chat: ChatService) {}

  ngOnInit() {
    this.chat.summary().then(
      (s) => this.summary.set(s),
      () => this.summary.set(null),
    );
  }

  ask(text: string) {
    this.draft = text;
    this.send();
  }

  async send() {
    const text = this.draft.trim();
    if (!text || this.busy()) return;
    this.draft = '';
    this.busy.set(true);
    this.status.set(null);

    this.messages.update((m) => [
      ...m,
      { role: 'user', text, tools: [] },
      { role: 'assistant', text: '', tools: [] },
    ]);
    this.scrollDown();

    const patchLast = (fn: (msg: ChatMessage) => ChatMessage) =>
      this.messages.update((m) => [...m.slice(0, -1), fn(m[m.length - 1])]);

    try {
      for await (const event of this.chat.send(text)) {
        if (event.type === 'thinking') {
          this.status.set('Thinking…');
        } else if (event.type === 'tool') {
          this.status.set(`${event.label}…`);
          patchLast((msg) => ({ ...msg, tools: [...msg.tools, event.label ?? event.name ?? ''] }));
        } else if (event.type === 'delta') {
          this.status.set(null);
          patchLast((msg) => ({ ...msg, text: msg.text + (event.text ?? '') }));
          this.scrollDown();
        } else if (event.type === 'error') {
          patchLast((msg) => ({ ...msg, text: event.message ?? 'Something went wrong.', error: true }));
        }
      }
    } catch (err) {
      patchLast((msg) => ({
        ...msg,
        text: err instanceof Error ? err.message : 'Could not reach the backend.',
        error: true,
      }));
    } finally {
      this.busy.set(false);
      this.status.set(null);
      this.scrollDown();
    }
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  private scrollDown() {
    setTimeout(() => {
      const el = this.scroller?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
}
