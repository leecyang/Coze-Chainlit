import capitalize from 'lodash/capitalize';
import {
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  ShieldCheck,
  UserRound
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';

import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

import { lingxiFetch } from './api';

const MIN_PASSWORD_LENGTH = 4;

type ProfileUser = {
  identifier: string;
  display_name?: string;
  metadata?: Record<string, unknown>;
};

type PasswordFieldProps = {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  autoComplete: string;
  disabled?: boolean;
  onChange: (value: string) => void;
};

function PasswordField({
  id,
  label,
  value,
  placeholder,
  autoComplete,
  disabled,
  onChange
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </Label>
      <div className="relative">
        <Input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className="pr-9"
        />
        <button
          type="button"
          tabIndex={-1}
          aria-label={visible ? '隐藏密码' : '显示密码'}
          onClick={() => setVisible((v) => !v)}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
    </div>
  );
}

export type UserProfileDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: ProfileUser;
};

export default function UserProfileDialog({
  open,
  onOpenChange,
  user
}: UserProfileDialogProps) {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const displayName = user.display_name || user.identifier;
  const avatarUrl = user.metadata?.image as string | undefined;
  const isAdmin = user.metadata?.role === 'admin';

  // Reset the form whenever the dialog is (re)opened.
  useEffect(() => {
    if (open) {
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setSubmitting(false);
    }
  }, [open]);

  const validationError = useMemo(() => {
    if (!currentPassword || !newPassword || !confirmPassword) return null;
    if (newPassword.length < MIN_PASSWORD_LENGTH)
      return `新密码长度不能少于 ${MIN_PASSWORD_LENGTH} 个字符`;
    if (newPassword === currentPassword) return '新密码不能与当前密码相同';
    if (newPassword !== confirmPassword) return '两次输入的新密码不一致';
    return null;
  }, [currentPassword, newPassword, confirmPassword]);

  const canSubmit =
    !submitting &&
    !!currentPassword &&
    !!newPassword &&
    !!confirmPassword &&
    !validationError;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const data = await lingxiFetch<{ success: boolean; message?: string }>(
        '/api/account/password',
        {
          method: 'POST',
          body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword
          })
        }
      );
      toast.success(data.message || '密码修改成功');
      onOpenChange(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '密码修改失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-0 overflow-hidden p-0 sm:max-w-[420px]">
        {/* Identity header */}
        <div className="bg-gradient-to-br from-[#9242eb] to-[#6d28d9] px-6 pb-5 pt-6 text-white">
          <div className="flex items-center gap-4">
            <Avatar className="size-14 border-2 border-white/40 shadow-sm">
              <AvatarImage src={avatarUrl} alt={displayName} />
              <AvatarFallback className="bg-white/20 text-lg font-semibold text-white">
                {capitalize(displayName[0])}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <DialogHeader className="space-y-1 text-left">
                <DialogTitle className="truncate text-lg font-semibold text-white">
                  {displayName}
                </DialogTitle>
                <DialogDescription className="truncate text-sm text-white/80">
                  {user.identifier}
                </DialogDescription>
              </DialogHeader>
            </div>
          </div>
          <Badge
            variant="secondary"
            className="mt-4 gap-1 border-none bg-white/20 text-white hover:bg-white/25"
          >
            {isAdmin ? (
              <ShieldCheck className="size-3.5" />
            ) : (
              <UserRound className="size-3.5" />
            )}
            {isAdmin ? '管理员' : '普通用户'}
          </Badge>
        </div>

        {/* Change-password section */}
        <div className="space-y-4 px-6 py-5">
          <div className="flex items-center gap-2">
            <KeyRound className="size-4 text-[#9242eb]" />
            <h3 className="text-sm font-semibold">修改登录密码</h3>
          </div>

          <div className="space-y-3">
            <PasswordField
              id="profile-current-password"
              label="当前密码"
              value={currentPassword}
              placeholder="请输入当前密码"
              autoComplete="current-password"
              disabled={submitting}
              onChange={setCurrentPassword}
            />
            <PasswordField
              id="profile-new-password"
              label="新密码"
              value={newPassword}
              placeholder={`至少 ${MIN_PASSWORD_LENGTH} 个字符`}
              autoComplete="new-password"
              disabled={submitting}
              onChange={setNewPassword}
            />
            <PasswordField
              id="profile-confirm-password"
              label="确认新密码"
              value={confirmPassword}
              placeholder="请再次输入新密码"
              autoComplete="new-password"
              disabled={submitting}
              onChange={setConfirmPassword}
            />
          </div>

          {validationError ? (
            <p className="text-xs text-destructive">{validationError}</p>
          ) : null}

          <div className="flex justify-end gap-2 pt-1">
            <Button
              variant="ghost"
              disabled={submitting}
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button
              disabled={!canSubmit}
              onClick={handleSubmit}
              className="bg-[#9242eb] text-white hover:bg-[#7c3aed]"
            >
              {submitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  保存中
                </>
              ) : (
                '保存修改'
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
