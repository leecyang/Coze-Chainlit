import { MessageAvatar } from './Message/Avatar';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '@/components/ui/accordion';
import { cn } from '@/lib/utils';

const dotClass = 'h-1.5 w-1.5 rounded-full bg-primary';

interface ReasoningPanelProps {
  reasoning?: string;
  isRunning?: boolean;
  className?: string;
}

const ThinkingDots = () => (
  <span className="flex items-center gap-1" aria-hidden="true">
    <span className={`${dotClass} animate-bounce`} />
    <span
      className={`${dotClass} animate-bounce`}
      style={{ animationDelay: '120ms' }}
    />
    <span
      className={`${dotClass} animate-bounce`}
      style={{ animationDelay: '240ms' }}
    />
  </span>
);

export function CozeReasoningPanel({
  reasoning,
  isRunning,
  className
}: ReasoningPanelProps) {
  const hasReasoning = Boolean(reasoning?.trim());

  if (!hasReasoning && !isRunning) {
    return null;
  }

  return (
    <Accordion
      type="single"
      collapsible
      className={cn(
        'w-full rounded-lg border border-border/70 bg-muted/40 px-3',
        className
      )}
    >
      <AccordionItem value="coze-reasoning" className="border-none">
        <AccordionTrigger className="py-2 text-sm text-muted-foreground hover:no-underline">
          <span className="flex items-center gap-2">
            <span>{isRunning ? '思考中' : '模型思考'}</span>
            {isRunning ? <ThinkingDots /> : null}
          </span>
        </AccordionTrigger>
        <AccordionContent className="pb-3">
          {hasReasoning ? (
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md bg-background/70 p-3 text-sm leading-6 text-foreground">
              {reasoning}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">
              正在等待模型思考输出
            </p>
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

export default function WaitingResponse() {
  return (
    <div className="step pt-0 pb-1">
      <div className="ai-message flex w-full gap-4">
        <MessageAvatar />
        <div className="mt-0.5 flex min-h-9 items-center gap-3 rounded-2xl bg-muted/60 px-4 py-2 text-sm text-muted-foreground">
          <span>思考中</span>
          <ThinkingDots />
        </div>
      </div>
    </div>
  );
}
