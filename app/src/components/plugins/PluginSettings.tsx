/**
 * Plugin settings component for configuring individual plugins.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ArrowLeft,
  Save,
  RefreshCw,
  Power,
  PowerOff,
  AlertCircle,
  CheckCircle,
  Wrench,
  Cloud,
  Layout,
  Link,
  Shield,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import {
  getPlugin,
  getPluginSettings,
  updatePluginSettings,
  getPluginTools,
  getPluginProviders,
  enablePlugin,
  disablePlugin,
  reloadPlugin,
} from '@/lib/api/plugins';
import type {
  PluginInfo,
  PluginSettings as PluginSettingsType,
  PluginTool,
  PluginProvider,
  PluginType,
  PluginPermission,
} from '@/types/plugin';
import { PLUGIN_TYPE_INFO, PERMISSION_INFO, getStatusVariant, getRiskColor } from '@/types/plugin';

const TYPE_ICONS: Record<PluginType, typeof Wrench> = {
  tool: Wrench,
  provider: Cloud,
  ui: Layout,
  integration: Link,
};

interface PluginSettingsProps {
  pluginId: string;
  onBack: () => void;
}

export function PluginSettings({ pluginId, onBack }: PluginSettingsProps) {
  const [plugin, setPlugin] = useState<PluginInfo | null>(null);
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [tools, setTools] = useState<PluginTool[]>([]);
  const [providers, setProviders] = useState<PluginProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const loadPlugin = useCallback(async () => {
    try {
      setLoading(true);
      const [pluginData, settingsData] = await Promise.all([
        getPlugin(pluginId),
        getPluginSettings(pluginId),
      ]);
      setPlugin(pluginData);
      setSettings(settingsData.settings);

      // Load tools and providers if plugin is loaded
      if (pluginData.is_loaded) {
        try {
          const [toolsData, providersData] = await Promise.all([
            getPluginTools(pluginId),
            getPluginProviders(pluginId),
          ]);
          setTools(toolsData);
          setProviders(providersData);
        } catch {
          // Plugin might not provide tools/providers
        }
      }
    } catch (error) {
      toast.error('Failed to load plugin');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [pluginId]);

  useEffect(() => {
    loadPlugin();
  }, [loadPlugin]);

  const handleSettingChange = (key: string, value: unknown) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await updatePluginSettings(pluginId, settings);
      toast.success('Settings saved');
      setHasChanges(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async () => {
    if (!plugin) return;

    try {
      if (plugin.status === 'enabled') {
        await disablePlugin(pluginId);
        toast.success('Plugin disabled');
      } else {
        await enablePlugin(pluginId);
        toast.success('Plugin enabled');
      }
      loadPlugin();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to toggle plugin');
    }
  };

  const handleReload = async () => {
    try {
      await reloadPlugin(pluginId);
      toast.success('Plugin reloaded');
      loadPlugin();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to reload plugin');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!plugin) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Plugin not found</p>
        <Button variant="outline" onClick={onBack} className="mt-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
      </div>
    );
  }

  const Icon = TYPE_ICONS[plugin.type];
  const isEnabled = plugin.status === 'enabled';
  const hasError = plugin.status === 'error';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={onBack}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex items-center gap-3 flex-1">
          <div className="p-2 rounded-lg bg-muted">
            <Icon className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-2xl font-bold">{plugin.name}</h2>
            <p className="text-muted-foreground">
              v{plugin.version} by {plugin.author.name}
            </p>
          </div>
        </div>
        <Badge variant={getStatusVariant(plugin.status)}>{plugin.status}</Badge>
      </div>

      {/* Error Banner */}
      {hasError && plugin.error_message && (
        <div className="flex items-start gap-3 p-4 rounded-lg bg-destructive/10 text-destructive">
          <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Plugin Error</p>
            <p className="text-sm">{plugin.error_message}</p>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Settings */}
        <div className="lg:col-span-2 space-y-6">
          {/* Plugin Controls */}
          <Card>
            <CardHeader>
              <CardTitle>Plugin Controls</CardTitle>
              <CardDescription>Enable, disable, or reload the plugin</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Enabled</Label>
                  <p className="text-sm text-muted-foreground">
                    {isEnabled ? 'Plugin is active and running' : 'Plugin is disabled'}
                  </p>
                </div>
                <Switch checked={isEnabled} onCheckedChange={() => handleToggle()} />
              </div>
              <Separator />
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleReload}
                  disabled={!isEnabled}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Reload Plugin
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Custom Settings */}
          {Object.keys(settings).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Settings</CardTitle>
                <CardDescription>Configure plugin-specific settings</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {Object.entries(settings).map(([key, value]) => (
                  <div key={key} className="space-y-2">
                    <Label htmlFor={key}>{formatSettingLabel(key)}</Label>
                    {typeof value === 'boolean' ? (
                      <Switch
                        id={key}
                        checked={value}
                        onCheckedChange={(checked) => handleSettingChange(key, checked)}
                      />
                    ) : (
                      <Input
                        id={key}
                        value={String(value ?? '')}
                        onChange={(e) => handleSettingChange(key, e.target.value)}
                      />
                    )}
                  </div>
                ))}
                <div className="pt-4">
                  <Button onClick={handleSave} disabled={!hasChanges || saving}>
                    <Save className="h-4 w-4 mr-2" />
                    {saving ? 'Saving...' : 'Save Settings'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Registered Tools */}
          {tools.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Registered Tools</CardTitle>
                <CardDescription>Tools provided by this plugin</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="flex items-start gap-3 p-3 rounded-lg bg-muted"
                    >
                      <Wrench className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="font-medium">{tool.name}</p>
                        <p className="text-sm text-muted-foreground">{tool.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Registered Providers */}
          {providers.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>AI Providers</CardTitle>
                <CardDescription>AI providers added by this plugin</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {providers.map((provider) => (
                    <div
                      key={provider.name}
                      className="flex items-start gap-3 p-3 rounded-lg bg-muted"
                    >
                      <Cloud className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="font-medium">{provider.display_name}</p>
                        <p className="text-sm text-muted-foreground">{provider.description}</p>
                        <div className="flex gap-2 mt-2">
                          {provider.supports_chat && (
                            <Badge variant="outline" className="text-xs">Chat</Badge>
                          )}
                          {provider.supports_embeddings && (
                            <Badge variant="outline" className="text-xs">Embeddings</Badge>
                          )}
                          {provider.supports_streaming && (
                            <Badge variant="outline" className="text-xs">Streaming</Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* About */}
          <Card>
            <CardHeader>
              <CardTitle>About</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">{plugin.description}</p>
              <Separator />
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Type</span>
                  <span>{PLUGIN_TYPE_INFO[plugin.type].label}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Version</span>
                  <span>{plugin.version}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Author</span>
                  <span>{plugin.author.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Installed</span>
                  <span>{new Date(plugin.installed_at).toLocaleDateString()}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Permissions */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Permissions
              </CardTitle>
              <CardDescription>
                Capabilities this plugin has access to
              </CardDescription>
            </CardHeader>
            <CardContent>
              {plugin.permissions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  This plugin requires no special permissions.
                </p>
              ) : (
                <div className="space-y-3">
                  {plugin.permissions.map((perm) => (
                    <PermissionItem key={perm} permission={perm} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function PermissionItem({ permission }: { permission: PluginPermission }) {
  const info = PERMISSION_INFO[permission];
  return (
    <div className="flex items-start gap-3">
      <div className={`mt-0.5 ${getRiskColor(info.risk)}`}>
        {info.risk === 'high' ? (
          <AlertCircle className="h-4 w-4" />
        ) : (
          <CheckCircle className="h-4 w-4" />
        )}
      </div>
      <div>
        <p className="text-sm font-medium">{info.label}</p>
        <p className="text-xs text-muted-foreground">{info.description}</p>
      </div>
    </div>
  );
}

function formatSettingLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}

export default PluginSettings;
