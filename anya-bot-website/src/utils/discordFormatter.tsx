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

  // FIRST: Extract HTML img tags before any other processing
  const imgRegex = /<img\s+[^>]*src=["']([^"']+)["'][^>]*>/gi;
  const imgTags: { placeholder: string; src: string; style?: string }[] = [];
  let imgIndex = 0;
  
  let processedText = text.replace(imgRegex, (match, src) => {
    const placeholder = `__IMG_${imgIndex++}__`;
    // Extract style attribute if present
    const styleMatch = match.match(/style=["']([^"']+)["']/i);
    const style = styleMatch ? styleMatch[1] : undefined;
    imgTags.push({ placeholder, src, style });
    return placeholder;
  });

  // Extract HTML span tags with styles
  const spanRegex = /<span\s+[^>]*style=["']([^"']+)["'][^>]*>([^<]*)<\/span>/gi;
  const spanTags: { placeholder: string; style: string; content: string }[] = [];
  let spanIndex = 0;
  
  processedText = processedText.replace(spanRegex, (_, style, content) => {
    const placeholder = `__SPAN_${spanIndex++}__`;
    spanTags.push({ placeholder, style, content });
    return placeholder;
  });

  // SECOND: Extract code blocks before any other processing to preserve them
  const codeBlockRegex = /```(\w+)?\s*([\s\S]*?)```/g;
  const codeBlocks: { placeholder: string; language: string; content: string }[] = [];
  let codeBlockIndex = 0;
  
  processedText = processedText.replace(codeBlockRegex, (_, lang, content) => {
    const placeholder = `__CODEBLOCK_${codeBlockIndex++}__`;
    codeBlocks.push({
      placeholder,
      language: (lang || '').trim().toLowerCase(),
      content: content || ''
    });
    return placeholder;
  });

  // Now handle blockquotes by processing line by line
  const lines = processedText.split('\n');
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
          {formatInlineMarkdown(groupText, codeBlocks, imgTags, spanTags)}
        </div>
      );
    } else {
      const formatted = formatInlineMarkdown(groupText, codeBlocks, imgTags, spanTags);
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
function formatInlineMarkdown(
  text: string, 
  codeBlocks: { placeholder: string; language: string; content: string }[] = [],
  imgTags: { placeholder: string; src: string; style?: string }[] = [],
  spanTags: { placeholder: string; style: string; content: string }[] = []
): React.ReactNode[] {
  if (!text) return [];

  const elements: React.ReactNode[] = [];
  let currentIndex = 0;
  let key = 0;

  // Regex patterns for Discord markdown
  // Order matters! Process placeholders first
  const patterns: PatternDefinition[] = [
    // Image placeholders (already extracted)
    ...imgTags.map((img) => ({
      regex: new RegExp(img.placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
      tag: 'img',
      transformer: () => ({
        content: img.src,
        meta: { src: img.src, style: img.style }
      })
    })),
    // Span placeholders (already extracted)
    ...spanTags.map((span) => ({
      regex: new RegExp(span.placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
      tag: 'span',
      transformer: () => ({
        content: span.content,
        meta: { style: span.style }
      })
    })),
    // Code block placeholders (already extracted)
    ...codeBlocks.map((cb) => ({
      regex: new RegExp(cb.placeholder.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
      tag: 'codeblock',
      transformer: () => ({
        content: cb.content,
        meta: { language: cb.language }
      })
    })),
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
    case 'img':
      {
        const src = typeof meta?.src === 'string' ? meta.src : content;
        const styleStr = typeof meta?.style === 'string' ? meta.style : '';
        // Parse inline style string to object
        const styleObj: React.CSSProperties = { width: '20px', height: '20px', display: 'inline-block', verticalAlign: 'middle' };
        if (styleStr) {
          styleStr.split(';').forEach(rule => {
            const [prop, val] = rule.split(':').map(s => s.trim());
            if (prop && val) {
              // Convert CSS property to camelCase
              const camelProp = prop.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
              (styleObj as Record<string, string>)[camelProp] = val;
            }
          });
        }
        return (
          <img 
            key={key} 
            src={src} 
            alt="" 
            className="inline-block align-middle"
            style={styleObj}
          />
        );
      }
    
    case 'span':
      {
        const styleStr = typeof meta?.style === 'string' ? meta.style : '';
        // Parse inline style string to object
        const styleObj: React.CSSProperties = {};
        if (styleStr) {
          styleStr.split(';').forEach(rule => {
            const [prop, val] = rule.split(':').map(s => s.trim());
            if (prop && val) {
              // Convert CSS property to camelCase
              const camelProp = prop.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
              (styleObj as Record<string, string>)[camelProp] = val;
            }
          });
        }
        return (
          <span key={key} style={styleObj}>
            {content}
          </span>
        );
      }
    
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
        return (
          <div key={key} className="my-2 rounded overflow-hidden bg-[#2b2d31] border border-[#1e1f22]">
            {language && (
              <div className="px-3 py-1 bg-[#1e1f22] text-[#949ba4] text-xs font-medium border-b border-[#1e1f22]">
                {language}
              </div>
            )}
            <pre className="p-3 text-sm font-mono overflow-x-auto whitespace-pre-wrap">
              <code className="text-[#dcddde] block">{content}</code>
            </pre>
          </div>
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
      const progressBar = String(meta?.progressBar || '▰▰▰▰▰▰▰▰▰▰');
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
  
  // Process the FULL text first to handle multi-line code blocks properly
  const formatted = formatDiscordText(children);
  
  return (
    <span className={className}>
      {formatted}
    </span>
  );
};
