import type React from 'react';

import { useChatInteract } from '@chainlit/react-client';

import { Translator } from '@/components/i18n';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip';

import { EditSquare } from '../icons/EditSquare';

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  navigate?: (to: string) => void;
  onConfirm?: () => void;
}

const NewChatButton = ({ navigate, onConfirm, ...buttonProps }: Props) => {
  const { clear } = useChatInteract();

  const handleClickOpen = () => {
    handleConfirm();
  };

  const handleConfirm = () => {
    if (onConfirm) {
      onConfirm();
    } else {
      clear();
      navigate?.('/');
    }
  };

  return (
    <div>
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              id="new-chat-button"
              className="text-muted-foreground hover:text-muted-foreground"
              onClick={handleClickOpen}
              {...buttonProps}
            >
              <EditSquare className="!size-6" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            <Translator path="navigation.newChat.dialog.tooltip" />
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
};

export default NewChatButton;
