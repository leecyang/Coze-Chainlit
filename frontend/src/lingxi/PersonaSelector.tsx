import { useEffect, useState } from 'react';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';

import { TargetRole, lingxiFetch } from './api';

const roles: TargetRole[] = ['新手小白', '辩论对手', '计网专家'];

export default function PersonaSelector() {
  const [value, setValue] = useState<TargetRole>('计网专家');

  useEffect(() => {
    lingxiFetch<{ target_role: TargetRole | '' }>('/api/target-role')
      .then((data) => {
        if (data.target_role) setValue(data.target_role);
      })
      .catch(() => undefined);
  }, []);

  const updateRole = async (nextRole: TargetRole) => {
    setValue(nextRole);
    await lingxiFetch('/api/target-role', {
      method: 'POST',
      body: JSON.stringify({ target_role: nextRole })
    });
  };

  return (
    <div className="flex items-center rounded-full px-1 py-1">
      <Select value={value} onValueChange={(v) => updateRole(v as TargetRole)}>
        <SelectTrigger
          aria-label="选择人设"
          className="h-8 w-[104px] rounded-full border-0 bg-transparent px-2 text-muted-foreground hover:bg-muted focus:ring-0 focus:ring-offset-0"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {roles.map((role) => (
            <SelectItem key={role} value={role}>
              {role}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
