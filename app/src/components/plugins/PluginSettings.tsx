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
  Eye,
  EyeOff,
  Coins,
  ExternalLink,
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
  const [showApiKey, setShowApiKey] = useState(false);
  const [clipperStatus, setClipperStatus] = useState<{
    connected: boolean;
    balance?: number;
    canGenerate?: boolean;
  } | null>(null);

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

  // For Clippy plugin, fetch connection status
  useEffect(() => {
    if (pluginId === 'clippy-integration' && plugin?.is_loaded) {
      fetchClipperStatus();
    }
  }, [pluginId, plugin?.is_loaded]);

  const fetchClipperStatus = async () => {
    try {
      const response = await fetch(`/api/plugins/clippy-integration/tools/clippy_status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ params: { refresh: true } }),
      });
      if (response.ok) {
        const data = await response.json();
        if (data.success && data.result) {
          setClipperStatus({
            connected: data.result.connected,
            balance: data.result.account?.credit_balance,
            canGenerate: data.result.account?.can_generate_clips,
          });
        }
      }
    } catch (e) {
      console.error('Failed to fetch Clipper status:', e);
    }
  };

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
          <div className="p-2 rounded-lg bg-muted overflow-hidden">
            {plugin.icon ? (
              <img
                src={`/api/plugins/${plugin.id}/icon`}
                alt={plugin.name}
                className="h-8 w-8 object-contain"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                  e.currentTarget.nextElementSibling?.classList.remove('hidden');
                }}
              />
            ) : null}
            <Icon className={`h-8 w-8 ${plugin.icon ? 'hidden' : ''}`} />
          </div>
          <div>
            <h2 className="text-xl font-bold">{plugin.name}</h2>
            <p className="text-sm text-muted-foreground">
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

          {/* Clippy-specific: Connection Status & Credits */}
          {pluginId === 'clippy-integration' && isEnabled && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2">
                  <Coins className="h-5 w-5" />
                  Clipper Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                {clipperStatus ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Connection</span>
                      <Badge variant={clipperStatus.connected ? 'default' : 'destructive'}>
                        {clipperStatus.connected ? 'Connected' : 'Disconnected'}
                      </Badge>
                    </div>
                    {clipperStatus.connected && clipperStatus.balance !== undefined && (
                      <>
                        <Separator />
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-muted-foreground">Credit Balance</span>
                          <span className={`text-lg font-semibold ${clipperStatus.canGenerate ? 'text-green-500' : 'text-amber-500'}`}>
                            {clipperStatus.balance.toLocaleString()} CLIP
                          </span>
                        </div>
                        {!clipperStatus.canGenerate && (
                          <p className="text-xs text-amber-500">
                            Insufficient credits for clip generation
                          </p>
                        )}
                      </>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={fetchClipperStatus}
                      className="w-full"
                    >
                      <RefreshCw className="h-4 w-4 mr-2" />
                      Refresh Status
                    </Button>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {settings.clipper_api_key ? 'Checking connection...' : 'Configure API key below to connect'}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Custom Settings */}
          {Object.keys(settings).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Configuration</CardTitle>
                <CardDescription>Plugin settings and credentials</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {Object.entries(settings).map(([key, value]) => {
                  const isApiKey = key.toLowerCase().includes('api_key') || key.toLowerCase().includes('apikey');
                  const isPassword = key.toLowerCase().includes('password') || key.toLowerCase().includes('secret');
                  const isUrl = key.toLowerCase().includes('url');
                  const isHidden = isApiKey || isPassword;
                  
                  return (
                    <div key={key} className="space-y-2">
                      <Label htmlFor={key} className="text-sm font-medium">
                        {formatSettingLabel(key)}
                      </Label>
                      {typeof value === 'boolean' ? (
                        <div className="flex items-center gap-3">
                          <Switch
                            id={key}
                            checked={value}
                            onCheckedChange={(checked) => handleSettingChange(key, checked)}
                          />
                          <span className="text-sm text-muted-foreground">
                            {value ? 'Enabled' : 'Disabled'}
                          </span>
                        </div>
                      ) : isHidden ? (
                        <div className="relative">
                          <Input
                            id={key}
                            type={showApiKey ? 'text' : 'password'}
                            value={String(value ?? '')}
                            onChange={(e) => handleSettingChange(key, e.target.value)}
                            placeholder={isApiKey ? 'Enter API key...' : 'Enter value...'}
                            className="pr-10"
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                            onClick={() => setShowApiKey(!showApiKey)}
                          >
                            {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </Button>
                        </div>
                      ) : (
                        <Input
                          id={key}
                          type={isUrl ? 'url' : typeof value === 'number' ? 'number' : 'text'}
                          value={String(value ?? '')}
                          onChange={(e) => handleSettingChange(key, typeof value === 'number' ? Number(e.target.value) : e.target.value)}
                          placeholder={isUrl ? 'https://...' : ''}
                        />
                      )}
                      {key === 'clipper_api_key' && (
                        <p className="text-xs text-muted-foreground">
                          Get your API key from the Clipper platform
                        </p>
                      )}
                    </div>
                  );
                })}
                <Separator />
                <Button onClick={handleSave} disabled={!hasChanges || saving} className="w-full">
                  <Save className="h-4 w-4 mr-2" />
                  {saving ? 'Saving...' : 'Save Settings'}
                </Button>
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
