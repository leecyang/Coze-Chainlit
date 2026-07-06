import { MessageAvatar } from './Message/Avatar';
import * as AccordionPrimitive from '@radix-ui/react-accordion';
import { Brain } from 'lucide-react';

import { cn } from '@/lib/utils';

const dotClass = 'h-1 w-1 rounded-full bg-muted-foreground/70';

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
    <AccordionPrimitive.Root
      type="single"
      collapsible
      className={cn(
        'w-full text-muted-foreground',
        className
      )}
    >
      <AccordionPrimitive.Item value="coze-reasoning">
        <AccordionPrimitive.Header className="flex">
          <AccordionPrimitive.Trigger className="group inline-flex max-w-full items-center gap-1.5 rounded-full px-1.5 py-1 text-xs text-muted-foreground/80 transition-colors hover:bg-muted/30 hover:text-muted-foreground">
            <Brain className="h-3.5 w-3.5 shrink-0" />
            <span>{isRunning ? '思考中' : '模型思考'}</span>
            {isRunning ? <ThinkingDots /> : null}
          </AccordionPrimitive.Trigger>
        </AccordionPrimitive.Header>
        <AccordionPrimitive.Content className="overflow-hidden data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down">
          {hasReasoning ? (
            <div className="max-h-72 overflow-y-auto pr-1 text-xs leading-5 text-muted-foreground/80 [scrollbar-width:thin]">
              <p className="whitespace-pre-wrap break-words">
              {reasoning}
              </p>
            </div>
          ) : (
            <p className="text-xs leading-5 text-muted-foreground/80">
              正在等待模型思考输出
            </p>
          )}
        </AccordionPrimitive.Content>
      </AccordionPrimitive.Item>
    </AccordionPrimitive.Root>
  );
}

export default function WaitingResponse() {
  return (
    <div className="step pt-0 pb-1">
      <div className="ai-message flex w-full gap-4">
        <MessageAvatar />
        <div className="mt-0.5 inline-flex min-h-8 items-center gap-2 rounded-full bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground">
          <Brain className="h-3.5 w-3.5" />
          <span>思考中</span>
          <ThinkingDots />
        </div>
      </div>
    </div>
  );
}
