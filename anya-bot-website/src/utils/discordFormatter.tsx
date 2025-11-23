import React from 'react';

interface PatternDefinition {
  regex: RegExp;
  tag: string;
  transformer?: (match: RegExpExecArray) => {
    content: string;
    meta?: Record<string, unknown>;
  };
}

/**
 * Formats Discord markdown text into React elements
 * Supports: **bold**, *italic*, __underline__, ~~strikethrough~~, `code`, ```code blocks```, ||spoiler||
 */
export function formatDiscordText(text: string): React.ReactNode[] {
  if (!text) return [];

  const elements: React.ReactNode[] = [];
  let currentIndex = 0;
  let key = 0;

  // Regex patterns for Discord markdown
  // Order matters! Process code blocks first to avoid conflicts
  const patterns: PatternDefinition[] = [
    {
      regex: /```(\w+)?\n?([\s\S]+?)```/g,
      tag: 'codeblock',
      transformer: (match) => ({
        content: match[2],
        meta: { language: (match[1] || '').trim().toLowerCase() },
      }),
    },
    { regex: /`([^`]+)`/g, tag: 'code' },                      // `code`
    { regex: /\*\*\*(.+?)\*\*\*/g, tag: 'bold-italic' },      // ***bold italic***
    { regex: /\*\*(.+?)\*\*/g, tag: 'bold' },                  // **bold**
    { regex: /\*(.+?)\*/g, tag: 'italic' },                    // *italic*
    { regex: /__(.+?)__/g, tag: 'underline' },                 // __underline__
    { regex: /~~(.+?)~~/g, tag: 'strikethrough' },             // ~~strikethrough~~
    { regex: /\|\|(.+?)\|\|/g, tag: 'spoiler' },               // ||spoiler||
    { regex: /<@!?(\d+)>/g, tag: 'mention' },                  // <@123456> mention
    { regex: /<#(\d+)>/g, tag: 'channel' },                    // <#123456> channel
    { regex: /<:(\w+):(\d+)>/g, tag: 'emoji' },                // <:name:123456> emoji
  ];

  // Find all matches
  const matches: Array<{ start: number; end: number; content: string; tag: string; meta?: Record<string, unknown> }> = [];

  patterns.forEach(({ regex, tag, transformer }) => {
    const regexCopy = new RegExp(regex.source, regex.flags);
    let match;
    
    while ((match = regexCopy.exec(text)) !== null) {
      const transformed = transformer
        ? transformer(match)
        : { content: match[1] || match[0], meta: undefined };
      matches.push({
        start: match.index,
        end: match.index + match[0].length,
        content: transformed.content,
        tag,
        meta: transformed.meta,
      });
    }
  });

  // Sort matches by start position
  matches.sort((a, b) => a.start - b.start);

  // Remove overlapping matches (keep first one)
  const filteredMatches = matches.filter((match, index) => {
    if (index === 0) return true;
    const prevMatch = matches[index - 1];
    return match.start >= prevMatch.end;
  });

  // Build elements
  filteredMatches.forEach(match => {
    // Add text before match
    if (currentIndex < match.start) {
      elements.push(
        <span key={key++}>{text.substring(currentIndex, match.start)}</span>
      );
    }

    // Add formatted element
    elements.push(formatElement(match.content, match.tag, key++, match.meta));
    currentIndex = match.end;
  });

  // Add remaining text
  if (currentIndex < text.length) {
    elements.push(
      <span key={key++}>{text.substring(currentIndex)}</span>
    );
  }

  return elements.length > 0 ? elements : [text];
}

function formatElement(content: string, tag: string, key: number, meta?: Record<string, unknown>): React.ReactNode {
  switch (tag) {
    case 'bold':
      return <strong key={key} className="font-bold">{content}</strong>;
    
    case 'italic':
      return <em key={key} className="italic">{content}</em>;
    
    case 'bold-italic':
      return <strong key={key} className="font-bold italic">{content}</strong>;
    
    case 'underline':
      return <span key={key} className="underline">{content}</span>;
    
    case 'strikethrough':
      return <span key={key} className="line-through opacity-75">{content}</span>;
    
    case 'code':
      return (
        <code key={key} className="px-1.5 py-0.5 bg-dark-700 text-primary rounded text-sm font-mono">
          {content}
        </code>
      );
    
    case 'codeblock':
      {
        const language = typeof meta?.language === 'string' ? meta.language : '';
        const languageClass = language ? `language-${language}` : '';
        return (
          <pre
            key={key}
            className={`my-2 p-3 bg-[#2b2d31] border border-dark-600 rounded text-sm font-mono overflow-x-auto whitespace-pre-wrap break-words ${languageClass}`.trim()}
            data-language={language || undefined}
          >
            <code className={`text-gray-300 ${languageClass}`.trim()}>{content.trim()}</code>
          </pre>
        );
      }
    
    case 'spoiler':
      return (
        <span 
          key={key} 
          className="px-1 bg-dark-700 text-dark-700 hover:text-white transition-colors cursor-pointer rounded"
          title="Click to reveal spoiler"
        >
          {content}
        </span>
      );
    
    case 'mention':
      return (
        <span key={key} className="px-1.5 py-0.5 bg-primary/20 text-primary rounded">
          @User
        </span>
      );
    
    case 'channel':
      return (
        <span key={key} className="px-1.5 py-0.5 bg-primary/20 text-primary rounded">
          #channel
        </span>
      );
    
    case 'emoji':
      return <span key={key}>:{content}:</span>;
    
    default:
      return <span key={key}>{content}</span>;
  }
}

/**
 * Component to render Discord-formatted text
 */
interface DiscordTextProps {
  children: string;
  className?: string;
}

export const DiscordText: React.FC<DiscordTextProps> = ({ children, className = '' }) => {
  return (
    <span className={className}>
      {formatDiscordText(children)}
    </span>
  );
};
