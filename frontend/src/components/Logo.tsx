import { cn } from '@/lib/utils';

import { useConfig } from '@chainlit/react-client';

interface Props {
  className?: string;
}

export const Logo = ({ className }: Props) => {
  const { config } = useConfig();
  const configuredLogoUrl = config?.ui?.logo_file_url;
  const logoUrl =
    configuredLogoUrl && configuredLogoUrl !== '/public/logo_backup.svg'
      ? configuredLogoUrl
      : '/public/logo_full_text.svg';

  return (
    <img
      src={logoUrl}
      alt="logo"
      className={cn('logo', className)}
    />
  );
};
