import { cn } from '@/lib/utils';
import { AlertCircle } from 'lucide-react';
import { useContext, useMemo } from 'react';

import {
  ChainlitContext,
  useChatSession,
  useConfig
} from '@chainlit/react-client';

import Icon from '@/components/Icon';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip';

const DEFAULT_AVATAR_SIZE = 32;

interface Props {
  author?: string;
  hide?: boolean;
  isError?: boolean;
  iconName?: string;
}

const MessageAvatar = ({ author, hide, isError, iconName }: Props) => {
  const apiClient = useContext(ChainlitContext);
  const { chatProfile } = useChatSession();
  const { config } = useConfig();

  const selectedChatProfile = useMemo(() => {
    return config?.chatProfiles.find((profile) => profile.name === chatProfile);
  }, [config, chatProfile]);

  const avatarUrl = useMemo(() => {
    if (config?.ui?.default_avatar_file_url)
      return config?.ui?.default_avatar_file_url;
    const isAssistant = !author || author === config?.ui.name;
    if (isAssistant && selectedChatProfile?.icon) {
      return selectedChatProfile.icon;
    }
    return apiClient?.buildEndpoint(`/avatars/${author || 'default'}`);
  }, [apiClient, selectedChatProfile, config, author]);

  const avatarSize = config?.ui?.avatar_size ?? DEFAULT_AVATAR_SIZE;
  const sizeStyle = { width: `${avatarSize}px`, height: `${avatarSize}px` };
  const fallbackLabel = (author || config?.ui?.name || 'AI')
    .trim()
    .charAt(0)
    .toUpperCase();

  if (isError) {
    return (
      <span className={cn('inline-flex shrink-0', hide && 'invisible')}>
        <AlertCircle
          className="mt-[3px] fill-destructive text-destructive-foreground"
          style={sizeStyle}
        />
      </span>
    );
  }

  // Render icon or avatar based on iconName
  const avatarContent = iconName ? (
    <span
      className="mt-[3px] inline-flex shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground"
      style={sizeStyle}
    >
      <Icon name={iconName} size={Math.max(18, avatarSize * 0.62)} />
    </span>
  ) : (
    <Avatar className="mt-[3px]" style={sizeStyle}>
      <AvatarImage
        src={avatarUrl}
        alt={`Avatar for ${author || 'default'}`}
        className="bg-transparent"
      />
      <AvatarFallback className="bg-primary/10 text-sm font-semibold text-primary">
        {fallbackLabel || <Skeleton className="h-full w-full rounded-full" />}
      </AvatarFallback>
    </Avatar>
  );

  return (
    <span className={cn('inline-flex shrink-0', hide && 'invisible')}>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>{avatarContent}</TooltipTrigger>
          <TooltipContent>
            <p>{author}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </span>
  );
};

export { MessageAvatar };
