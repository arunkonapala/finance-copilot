import { Pipe, PipeTransform, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/** Minimal markdown renderer for assistant messages: escapes HTML first,
 *  then supports headings, bold/italic, inline code, code blocks, and lists. */
@Pipe({ name: 'markdown' })
export class MarkdownPipe implements PipeTransform {
  private sanitizer = inject(DomSanitizer);

  transform(value: string): SafeHtml {
    let text = (value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) => `<pre>${code}</pre>`);
    text = text.replace(/`([^`\n]+)`/g, '<code>$1</code>');
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/(^|\s)\*([^*\n]+)\*(?=\s|[.,!?]|$)/g, '$1<em>$2</em>');

    const lines = text.split('\n');
    const out: string[] = [];
    let listMode: 'ul' | 'ol' | null = null;
    const closeList = () => {
      if (listMode) out.push(`</${listMode}>`);
      listMode = null;
    };
    for (const line of lines) {
      const h = line.match(/^(#{1,4})\s+(.*)$/);
      const ul = line.match(/^\s*[-•*+]\s+(.*)$/);
      const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (h) {
        closeList();
        const level = Math.min(h[1].length + 2, 5);
        out.push(`<h${level}>${h[2]}</h${level}>`);
      } else if (ul) {
        if (listMode !== 'ul') { closeList(); out.push('<ul>'); listMode = 'ul'; }
        out.push(`<li>${ul[1]}</li>`);
      } else if (ol) {
        if (listMode !== 'ol') { closeList(); out.push('<ol>'); listMode = 'ol'; }
        out.push(`<li>${ol[1]}</li>`);
      } else if (line.trim() === '') {
        closeList();
        out.push('<br>');
      } else {
        closeList();
        out.push(`<p>${line}</p>`);
      }
    }
    closeList();
    return this.sanitizer.bypassSecurityTrustHtml(out.join(''));
  }
}
