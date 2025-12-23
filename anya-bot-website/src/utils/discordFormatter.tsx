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
 * Supports: **bold**, *italic*, __underline__, ~~strikethrough~~, `code`, ```code blocks```, ||spoiler||, > blockquote
 */
export function formatDiscordText(text: string): React.ReactNode[] {
  if (!text) return [];

  // First, handle blockquotes by processing line by line
  const lines = text.split('\n');
  const processedLines: { content: string; isBlockquote: boolean }[] = [];
  
  for (const line of lines) {
    if (line.startsWith('> ')) {
      processedLines.push({ content: line.substring(2), isBlockquote: true });
    } else if (line === '>') {
      processedLines.push({ content: '', isBlockquote: true });
    } else {
      processedLines.push({ content: line, isBlockquote: false });
    }
  }

  // Group consecutive blockquote lines
  const groups: { lines: string[]; isBlockquote: boolean }[] = [];
  for (const line of processedLines) {
    const lastGroup = groups[groups.length - 1];
    if (lastGroup && lastGroup.isBlockquote === line.isBlockquote) {
      lastGroup.lines.push(line.content);
    } else {
      groups.push({ lines: [line.content], isBlockquote: line.isBlockquote });
    }
  }

  // Process each group
  const result: React.ReactNode[] = [];
  let groupKey = 0;
  
  for (const group of groups) {
    const groupText = group.lines.join('\n');
    if (group.isBlockquote) {
      result.push(
        <div 
          key={`blockquote-${groupKey++}`}
          className="pl-3 border-l-4 border-[#4e5058] my-1"
        >
          {formatInlineMarkdown(groupText)}
        </div>
      );
    } else {
      const formatted = formatInlineMarkdown(groupText);
      if (formatted.length > 0) {
        result.push(<span key={`text-${groupKey++}`}>{formatted}</span>);
      }
    }
  }

  return result.length > 0 ? result : [text];
}

/**
 * Formats inline Discord markdown (everything except blockquotes)
 */
function formatInlineMarkdown(text: string): React.ReactNode[] {
  if (!text) return [];

  const elements: React.ReactNode[] = [];
  let currentIndex = 0;
  let key = 0;

  // Regex patterns for Discord markdown
  // Order matters! Process code blocks first to avoid conflicts
  const patterns: PatternDefinition[] = [
    {
      // Score with progress bar (e.g., "Score: 7.1/10▰▰▰▰▰▰▰▱▱▱")
      regex: /(Score:?|Rating:?)\s*([\d.]+)\s*\/\s*(\d+)[\s\n]*([▰▱]+)/g,
      tag: 'score',
      transformer: (match) => ({
        content: match[0],
        meta: {
          label: match[1].trim(),
          score: parseFloat(match[2]),
          max: parseInt(match[3], 10),
          progressBar: match[4].trim()
        }
      }),
    },
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

  return elements.length > 0 ? elements : [<span key="plain">{text}</span>];
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
      
    case 'score':
      const score = typeof meta?.score === 'number' ? meta.score : 0;
      const max = typeof meta?.max === 'number' ? meta.max : 10;
      const progressBar = meta?.progressBar || '▰▰▰▰▰▰▰▰▰▰';
      const percentage = Math.min(Math.max((score / max) * 100, 0), 100);
      
      return (
        <div key={key} className="my-2">
          <div className="text-sm text-gray-300">
            <span className="font-medium">Score:</span> {score.toFixed(1)}/{max}
          </div>
          <div className="flex items-center mt-1">
            <div className="flex-1 h-5 bg-dark-700 rounded overflow-hidden relative">
              <div 
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${percentage}%` }}
              />
              <div className="absolute inset-0 flex items-center px-1">
                <span className="text-sm font-mono tracking-wider">
                  {progressBar}
                </span>
              </div>
            </div>
            <span className="ml-2 text-xs text-gray-400 w-10 text-right">
              {percentage.toFixed(0)}%
            </span>
          </div>
        </div>
      );
    
    default:
      return <span key={key}>{content}</span>;
  }
}

/**
 * Component to render Discord-formatted text with HTML support
 */
interface DiscordTextProps {
  children: string;
  className?: string;
}

export const DiscordText: React.FC<DiscordTextProps> = ({ children, className = '' }) => {
  if (!children) return null;
  
  // Split by newlines first to handle them properly
  const lines = children.split('\n');
  
  return (
    <span className={className}>
      {lines.map((line, i) => {
        // Check if the line contains HTML
        const hasHtml = /<[a-z][\s\S]*>/i.test(line);
        
        if (!hasHtml) {
          // For non-HTML lines, just use the markdown formatter
          return (
            <React.Fragment key={i}>
              {i > 0 && <br />}
              {formatDiscordText(line)}
            </React.Fragment>
          );
        }
        
        // For lines with HTML, process them
        const parts: React.ReactNode[] = [];
        let lastIndex = 0;
        const htmlTagRegex = /(<\/?[a-z][^>]*>)/gi;
        let match;
        let matchCount = 0;
        
        // Split by HTML tags
        while ((match = htmlTagRegex.exec(line)) !== null) {
          // Add text before the HTML tag with markdown
          const textBefore = line.slice(lastIndex, match.index);
          if (textBefore) {
            parts.push(...formatDiscordText(textBefore));
          }
          
          // Skip processing if it's a closing span tag
          if (match[0].toLowerCase() !== '</span>') {
            parts.push(
              <span 
                key={`html-${i}-${matchCount++}`}
                dangerouslySetInnerHTML={{ __html: match[0] }}
              />
            );
          }
          
          lastIndex = htmlTagRegex.lastIndex;
        }
        
        // Add any remaining text after the last HTML tag
        if (lastIndex < line.length) {
          const remainingText = line.slice(lastIndex);
          // Only process if there's actual content (not just whitespace or closing tags)
          if (remainingText.trim() && remainingText.trim() !== '</span>') {
            parts.push(...formatDiscordText(remainingText));
          }
        }
        
        return (
          <React.Fragment key={i}>
            {i > 0 && <br />}
            {parts}
          </React.Fragment>
        );
      })}
    </span>
  );
};
