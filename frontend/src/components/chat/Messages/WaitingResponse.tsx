import { MessageAvatar } from './Message/Avatar';

const dotClass = 'h-1.5 w-1.5 rounded-full bg-primary';

export default function WaitingResponse() {
  return (
    <div className="step pt-0 pb-1">
      <div className="ai-message flex w-full gap-4">
        <MessageAvatar />
        <div className="mt-0.5 flex min-h-9 items-center gap-3 rounded-2xl bg-muted/60 px-4 py-2 text-sm text-muted-foreground">
          <span>思考中</span>
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
        </div>
      </div>
    </div>
  );
}
