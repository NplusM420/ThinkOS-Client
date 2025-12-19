/**
 * Smart Inbox component for viewing and managing inbox items.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Inbox,
  FileText,
  Link,
  Clock,
  CheckSquare,
  Bell,
  Bot,
  Lightbulb,
  RefreshCw,
  CheckCheck,
  Filter,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import {
  listInboxItems,
  getInboxStats,
  markAllAsRead,
  generateDigest,
  analyzeConnections,
  extractActions,
} from '@/lib/api/inbox';
import type { InboxItem, InboxStats, InboxItemType } from '@/types/inbox';
import { InboxCard } from './InboxCard';

const TYPE_ICONS: Record<InboxItemType, typeof FileText> = {
  digest: FileText,
  connection: Link,
  stale_alert: Clock,
  action_item: CheckSquare,
  reminder: Bell,
  agent_result: Bot,
  suggestion: Lightbulb,
};

interface SmartInboxProps {
  onViewMemory?: (memoryId: number) => void;
}

export function SmartInbox({ onViewMemory }: SmartInboxProps) {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [stats, setStats] = useState<InboxStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | InboxItemType>('all');
  const [generating, setGenerating] = useState(false);

  const loadInbox = useCallback(async () => {
    try {
      setLoading(true);
      const [itemsResponse, statsResponse] = await Promise.all([
        listInboxItems({
          itemType: activeTab === 'all' ? undefined : activeTab,
          limit: 50,
        }),
        getInboxStats(),
      ]);
      setItems(itemsResponse.items);
      setStats(statsResponse);
    } catch (error) {
      toast.error('Failed to load inbox');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadInbox();
  }, [loadInbox]);

  const handleMarkAllRead = async () => {
    try {
      const result = await markAllAsRead();
      toast.success(`Marked ${result.updated} items as read`);
      loadInbox();
    } catch (error) {
      toast.error('Failed to mark all as read');
    }
  };

  const handleGenerateDigest = async () => {
    try {
      setGenerating(true);
      const result = await generateDigest();
      if (result.generated) {
        toast.success('Digest generated');
        loadInbox();
      } else {
        toast.info(result.reason || 'No activity to summarize');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate digest');
    } finally {
      setGenerating(false);
    }
  };

  const handleAnalyzeConnections = async () => {
    try {
      setGenerating(true);
      const result = await analyzeConnections();
      toast.success(`Found ${result.suggestions_found} connections`);
      loadInbox();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to analyze connections');
    } finally {
      setGenerating(false);
    }
  };

  const handleExtractActions = async () => {
    try {
      setGenerating(true);
      const result = await extractActions();
      toast.success(`Found ${result.actions_found} action items`);
      loadInbox();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to extract actions');
    } finally {
      setGenerating(false);
    }
  };

  const handleItemUpdate = () => {
    loadInbox();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Inbox className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-bold">Smart Inbox</h2>
            <p className="text-muted-foreground">
              {stats ? (
                <>
                  {stats.unread} unread · {stats.actionable} actionable
                </>
              ) : (
                'Loading...'
              )}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" disabled={generating}>
                <Sparkles className="h-4 w-4 mr-2" />
                Generate
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleGenerateDigest}>
                <FileText className="h-4 w-4 mr-2" />
                Generate Digest
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleAnalyzeConnections}>
                <Link className="h-4 w-4 mr-2" />
                Find Connections
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleExtractActions}>
                <CheckSquare className="h-4 w-4 mr-2" />
                Extract Actions
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant="outline"
            size="sm"
            onClick={handleMarkAllRead}
            disabled={!stats?.unread}
          >
            <CheckCheck className="h-4 w-4 mr-2" />
            Mark All Read
          </Button>
          <Button variant="outline" size="sm" onClick={loadInbox}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v: string) => setActiveTab(v as typeof activeTab)}>
        <TabsList>
          <TabsTrigger value="all" className="gap-2">
            All
            {stats && stats.total > 0 && (
              <Badge variant="secondary" className="ml-1">
                {stats.total}
              </Badge>
            )}
          </TabsTrigger>
          {stats &&
            Object.entries(stats.by_type).map(([type, count]) => {
              const Icon = TYPE_ICONS[type as InboxItemType];
              return (
                <TabsTrigger key={type} value={type} className="gap-2">
                  {Icon && <Icon className="h-4 w-4" />}
                  {count > 0 && (
                    <Badge variant="secondary" className="ml-1">
                      {count}
                    </Badge>
                  )}
                </TabsTrigger>
              );
            })}
        </TabsList>

        <TabsContent value={activeTab} className="mt-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <EmptyInbox activeTab={activeTab} />
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <InboxCard
                  key={item.id}
                  item={item}
                  onUpdate={handleItemUpdate}
                  onViewMemory={onViewMemory}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function EmptyInbox({ activeTab }: { activeTab: string }) {
  return (
    <div className="text-center py-12">
      <Inbox className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
      <h3 className="text-lg font-medium mb-2">
        {activeTab === 'all' ? 'Your inbox is empty' : `No ${activeTab.replace('_', ' ')} items`}
      </h3>
      <p className="text-muted-foreground text-sm max-w-md mx-auto">
        {activeTab === 'all'
          ? 'ThinkOS will surface relevant insights, connections, and action items here.'
          : 'Items of this type will appear here when generated.'}
      </p>
    </div>
  );
}

export default SmartInbox;
