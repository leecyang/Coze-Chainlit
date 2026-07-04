import { useEffect, useState } from 'react';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from '@/components/ui/select';

import { PreferredStyle, lingxiFetch } from './api';

const styles: Array<{ value: PreferredStyle; label: string }> = [
  { value: 'auto', label: '自动' },
  { value: 'novice', label: '新手小白' },
  { value: 'debate', label: '辩论对手' },
  { value: 'expert', label: '计网专家' }
];

export default function PersonaSelector() {
  const [value, setValue] = useState<PreferredStyle>('auto');

  useEffect(() => {
    lingxiFetch<{ preferred_style: PreferredStyle | '' }>('/api/preferred-style')
      .then((data) => {
        if (data.preferred_style) setValue(data.preferred_style);
      })
      .catch(() => undefined);
  }, []);

  const updateStyle = (nextStyle: PreferredStyle) => {
    setValue(nextStyle);
    lingxiFetch('/api/preferred-style', {
      method: 'POST',
      body: JSON.stringify({ preferred_style: nextStyle })
    }).catch(() => undefined);
  };

  return (
    <div className="flex items-center rounded-full px-1 py-1">
      <Select value={value} onValueChange={(v) => updateStyle(v as PreferredStyle)}>
        <SelectTrigger
          aria-label="选择偏好风格"
          className="h-8 w-[104px] rounded-full border-0 bg-transparent px-2 text-muted-foreground hover:bg-muted focus:ring-0 focus:ring-offset-0"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {styles.map((style) => (
            <SelectItem key={style.value} value={style.value}>
              {style.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
