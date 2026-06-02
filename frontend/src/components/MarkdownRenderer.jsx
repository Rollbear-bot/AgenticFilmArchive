import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Renders markdown content with GitHub Flavored Markdown support.
 * Used for agent/assistant messages that contain markdown formatting.
 */
function MarkdownRenderer({ content }) {
  if (!content) return null;

  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Code blocks (```language\ncode\n```)
          code({ className, children, ...props }) {
            // Fenced code blocks have language-xxx className; inline code does not
            const match = /language-(\w+)/.exec(className || '');

            if (match) {
              return (
                <div className="code-block-wrapper">
                  {match && (
                    <div className="code-block-lang">{match[1]}</div>
                  )}
                  <pre className="code-block-pre">
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                </div>
              );
            }

            return (
              <code className="inline-code" {...props}>
                {children}
              </code>
            );
          },
          // Make links open in new tab
          a({ href, children, ...props }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            );
          },
          // Style tables
          table({ children, ...props }) {
            return (
              <div className="table-wrapper">
                <table {...props}>{children}</table>
              </div>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default MarkdownRenderer;
