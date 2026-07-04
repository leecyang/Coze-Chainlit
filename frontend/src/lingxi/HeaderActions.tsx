import { Shield } from 'lucide-react';

import { Button } from '@/components/ui/button';

import LeaderboardDialog from './LeaderboardDialog';

export default function LingxiHeaderActions() {
  return (
    <>
      <LeaderboardDialog />
      <Button
        asChild
        variant="ghost"
        size="icon"
        title="管理后台"
        className="text-muted-foreground hover:text-muted-foreground"
      >
        <a href="/admin">
          <Shield className="!size-5" />
        </a>
      </Button>
    </>
  );
}
