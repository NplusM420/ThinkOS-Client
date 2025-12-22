/**
 * Plugin browser component for discovering and managing plugins.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Wrench,
  Cloud,
  Layout,
  Link,
  Upload,
  RefreshCw,
  Trash2,
  Power,
  PowerOff,
  AlertCircle,
  CheckCircle,
  Settings,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import {
  listPlugins,
  uploadPlugin,
  uninstallPlugin,
  enablePlugin,
  disablePlugin,
  reloadPlugin,
} from '@/lib/api/plugins';
import type { PluginInfo, PluginType, PluginPermission } from '@/types/plugin';
import { PLUGIN_TYPE_INFO, PERMISSION_INFO, getStatusVariant, getRiskColor } from '@/types/plugin';

const TYPE_ICONS: Record<PluginType, typeof Wrench> = {
  tool: Wrench,
  provider: Cloud,
  ui: Layout,
  integration: Link,
};

interface PluginBrowserProps {
  onSelectPlugin?: (plugin: PluginInfo) => void;
}

export function PluginBrowser({ onSelectPlugin }: PluginBrowserProps) {
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<PluginType | 'all'>('all');
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedPlugin, setSelectedPlugin] = useState<PluginInfo | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadPlugins = useCallback(async () => {
    try {
      setLoading(true);
      const response = await listPlugins();
      setPlugins(response.plugins);
    } catch (error) {
      toast.error('Failed to load plugins');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPlugins();
  }, [loadPlugins]);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      const plugin = await uploadPlugin(file);
      toast.success(`Plugin "${plugin.name}" installed successfully`);
      setUploadDialogOpen(false);
      loadPlugins();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to upload plugin');
    } finally {
      setUploading(false);
    }
  };

  const handleToggleEnabled = async (plugin: PluginInfo) => {
    try {
      if (plugin.status === 'enabled') {
        await disablePlugin(plugin.id);
        toast.success(`Plugin "${plugin.name}" disabled`);
      } else {
        await enablePlugin(plugin.id);
        toast.success(`Plugin "${plugin.name}" enabled`);
      }
      loadPlugins();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to toggle plugin');
    }
  };

  const handleUninstall = async () => {
    if (!selectedPlugin) return;

    try {
      await uninstallPlugin(selectedPlugin.id);
      toast.success(`Plugin "${selectedPlugin.name}" uninstalled`);
      setDeleteDialogOpen(false);
      setSelectedPlugin(null);
      loadPlugins();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to uninstall plugin');
    }
  };

  const handleReload = async (plugin: PluginInfo) => {
    try {
      await reloadPlugin(plugin.id);
      toast.success(`Plugin "${plugin.name}" reloaded`);
      loadPlugins();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to reload plugin');
    }
  };

  const filteredPlugins = plugins.filter((plugin) => {
    const matchesSearch =
      plugin.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      plugin.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === 'all' || plugin.type === filterType;
    return matchesSearch && matchesType;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Plugins</h2>
          <p className="text-muted-foreground">
            Extend ThinkOS with community plugins
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={loadPlugins}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button size="sm" onClick={() => setUploadDialogOpen(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Install Plugin
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <Input
          placeholder="Search plugins..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-sm"
        />
        <div className="flex gap-1">
          <Button
            variant={filterType === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterType('all')}
          >
            All
          </Button>
          {(Object.keys(PLUGIN_TYPE_INFO) as PluginType[]).map((type) => {
            const Icon = TYPE_ICONS[type];
            return (
              <Button
                key={type}
                variant={filterType === type ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilterType(type)}
              >
                <Icon className="h-4 w-4 mr-1" />
                {PLUGIN_TYPE_INFO[type].label}
              </Button>
            );
          })}
        </div>
      </div>

      {/* Plugin Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : filteredPlugins.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground">
            {plugins.length === 0
              ? 'No plugins installed. Upload a plugin to get started.'
              : 'No plugins match your search.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredPlugins.map((plugin) => (
            <PluginCard
              key={plugin.id}
              plugin={plugin}
              onToggle={() => handleToggleEnabled(plugin)}
              onReload={() => handleReload(plugin)}
              onUninstall={() => {
                setSelectedPlugin(plugin);
                setDeleteDialogOpen(true);
              }}
              onSettings={() => onSelectPlugin?.(plugin)}
            />
          ))}
        </div>
      )}

      {/* Upload Dialog */}
      <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Install Plugin</DialogTitle>
            <DialogDescription>
              Upload a plugin archive (.zip) to install it.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Input
              type="file"
              accept=".zip,.tar.gz"
              onChange={handleUpload}
              disabled={uploading}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setUploadDialogOpen(false)}
              disabled={uploading}
            >
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Uninstall Plugin</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to uninstall "{selectedPlugin?.name}"? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleUninstall}>Uninstall</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

interface PluginCardProps {
  plugin: PluginInfo;
  onToggle: () => void;
  onReload: () => void;
  onUninstall: () => void;
  onSettings?: () => void;
}

function PluginCard({ plugin, onToggle, onReload, onUninstall, onSettings }: PluginCardProps) {
  const Icon = TYPE_ICONS[plugin.type];
  const isEnabled = plugin.status === 'enabled';
  const hasError = plugin.status === 'error';

  return (
    <div
      className={`flex items-center gap-4 p-4 rounded-lg border bg-card hover:bg-muted/50 transition-colors ${
        hasError ? 'border-destructive' : 'border-border'
      }`}
    >
      {/* Icon */}
      <div className="p-2.5 rounded-lg bg-muted flex-shrink-0 overflow-hidden">
        {plugin.icon ? (
          <img
            src={`/api/plugins/${plugin.id}/icon`}
            alt={plugin.name}
            className="h-5 w-5 object-contain"
            onError={(e) => {
              e.currentTarget.style.display = 'none';
              e.currentTarget.nextElementSibling?.classList.remove('hidden');
            }}
          />
        ) : null}
        <Icon className={`h-5 w-5 ${plugin.icon ? 'hidden' : ''}`} />
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="font-medium truncate">{plugin.name}</h3>
          <Badge variant={getStatusVariant(plugin.status)} className="text-xs">
            {plugin.status}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground mt-0.5">
          v{plugin.version} by {plugin.author.name}
        </p>
        <p className="text-sm text-muted-foreground mt-1 line-clamp-1">
          {plugin.description}
        </p>
        {hasError && plugin.error_message && (
          <p className="text-xs text-destructive mt-1 line-clamp-1">
            {plugin.error_message}
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          title={isEnabled ? 'Disable' : 'Enable'}
          className="h-8 w-8"
        >
          {isEnabled ? (
            <PowerOff className="h-4 w-4" />
          ) : (
            <Power className="h-4 w-4" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onReload}
          title="Reload"
          disabled={!isEnabled}
          className="h-8 w-8"
        >
          <RefreshCw className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onUninstall}
          title="Uninstall"
          className="h-8 w-8 text-destructive hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
        {onSettings && (
          <Button variant="outline" size="sm" onClick={onSettings} className="ml-2">
            <Settings className="h-4 w-4 mr-1.5" />
            Configure
          </Button>
        )}
      </div>
    </div>
  );
}

function PermissionBadge({ permission }: { permission: PluginPermission }) {
  const info = PERMISSION_INFO[permission];
  return (
    <Badge
      variant="outline"
      className={`text-xs ${getRiskColor(info.risk)}`}
      title={info.description}
    >
      {info.label}
    </Badge>
  );
}

export default PluginBrowser;
