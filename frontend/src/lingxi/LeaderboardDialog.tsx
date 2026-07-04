import { Trophy } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '@/components/ui/table';

import { LeaderboardEntry, lingxiFetch } from './api';

export default function LeaderboardDialog() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    lingxiFetch<{ leaderboard: LeaderboardEntry[] }>(
      '/v1/practice/leaderboard?limit=20&period=all'
    )
      .then((data) => setItems(data.leaderboard || []))
      .finally(() => setLoading(false));
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" title="排行榜">
          <Trophy className="!size-5" />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>学习排行榜</DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            加载中...
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>排名</TableHead>
                <TableHead>用户名</TableHead>
                <TableHead>总分</TableHead>
                <TableHead>最高分</TableHead>
                <TableHead>次数</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.length ? (
                items.map((item, index) => (
                  <TableRow key={item.username}>
                    <TableCell>{item.rank || index + 1}</TableCell>
                    <TableCell>{item.username}</TableCell>
                    <TableCell>{item.total_score || 0}</TableCell>
                    <TableCell>{item.highest_score || 0}</TableCell>
                    <TableCell>{item.practice_count || 0}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={5} className="text-center">
                    暂无排行数据
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </DialogContent>
    </Dialog>
  );
}
