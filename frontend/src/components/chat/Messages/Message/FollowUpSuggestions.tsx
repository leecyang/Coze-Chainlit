import { MessageCircleQuestion } from 'lucide-react';
import { useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';

import {
  IStep,
  useAuth,
  useChatData,
  useChatInteract
} from '@chainlit/react-client';

import { Button } from '@/components/ui/button';

interface Props {
  suggestions?: string[];
}

export default function FollowUpSuggestions({ suggestions }: Props) {
  const { sendMessage } = useChatInteract();
  const { loading, connected } = useChatData();
  const { user } = useAuth();

  const visibleSuggestions = (suggestions || [])
    .map((suggestion) => suggestion.trim())
    .filter(Boolean)
    .slice(0, 3);

  const onSelect = useCallback(
    (suggestion: string) => {
      const message: IStep = {
        threadId: '',
        id: uuidv4(),
        name: user?.identifier || 'User',
        type: 'user_message',
        output: suggestion,
        createdAt: new Date().toISOString(),
        metadata: { location: window.location.href }
      };

      sendMessage(message, []);
    },
    [sendMessage, user]
  );

  if (!visibleSuggestions.length) {
    return null;
  }

  return (
    <div className="mt-1 flex max-w-full flex-col gap-2">
      <p className="text-xs text-muted-foreground">你可以继续问</p>
      <div className="flex max-w-full flex-wrap gap-2">
        {visibleSuggestions.map((suggestion) => (
          <Button
            key={suggestion}
            type="button"
            variant="outline"
            className="h-auto max-w-full justify-start gap-2 rounded-2xl px-3 py-2 text-left text-sm font-normal"
            disabled={loading || !connected}
            onClick={() => onSelect(suggestion)}
          >
            <MessageCircleQuestion className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0 whitespace-normal break-words">
              {suggestion}
            </span>
          </Button>
        ))}
      </div>
    </div>
  );
}
