"use client";

import { UpgradePrompt } from "@/components/upgrade-prompt";
import { alertDraftPath, alertUpdate, readAlertDraft } from "@/lib/task-context";
import { currentReturnPath, withReturnPath } from "@/lib/return-path";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiError,
  fetchMe,
  type Me,
  fetchAlertSettings,
  fetchNotifications,
  getToken,
  markAllNotificationsRead,
  markNotificationRead,
  updateAlertSettings,
  type AlertSettings,
  type NotificationItem,
} from "@/lib/auth";

export default function NotificationsPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [draft, setDraft] = useState(false);
  const [advancedDenied, setAdvancedDenied] = useState(false);
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [settings, setSettings] = useState<AlertSettings | null>(null);
  const [threshold, setThreshold] = useState("5");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace(withReturnPath("/login", currentReturnPath()));
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([fetchNotifications(), fetchAlertSettings(), fetchMe()])
      .then(([notifications, alertSettings, profile]) => {
        if (!active) return;
        setMe(profile);
        const restored = readAlertDraft(new URLSearchParams(window.location.search));
        setDraft(Object.keys(restored).length > 0);
        setItems(notifications.items);
        setUnread(notifications.unread);
        setSettings({ ...alertSettings, ...restored });
        setThreshold(String(restored.price_pct ?? alertSettings.price_pct));
      })
      .catch((cause) => {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) router.replace(withReturnPath("/login", currentReturnPath()));
        else setError("提醒暂时无法加载，请重试。");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [router, attempt]);

  const premium = Boolean(me?.entitlements.capabilities.advanced_alerts) && !advancedDenied;

  useEffect(() => {
    if (!draft || !settings) return;
    const value = Number(threshold);
    if (!Number.isFinite(value) || value < 1 || value > 20) return;
    window.history.replaceState(null, "", alertDraftPath({ ...settings, price_pct: value }));
  }, [settings, threshold, draft]);

  function editSettings(next: AlertSettings) {
    setDraft(true);
    setSettings(next);
    setMessage(null);
  }

  async function onRead(id: number) {
    await markNotificationRead(id);
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, read: true } : item)),
    );
    setUnread((value) => Math.max(0, value - 1));
  }

  async function onReadAll() {
    await markAllNotificationsRead();
    setItems((current) => current.map((item) => ({ ...item, read: true })));
    setUnread(0);
  }

  async function onSaveSettings() {
    if (!settings) return;
    const value = Number(threshold);
    if (!Number.isFinite(value) || value < 1 || value > 20) {
      setError("涨跌阈值需在 1–20% 之间");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await updateAlertSettings(alertUpdate({
        price_pct: value,
        dividend: settings.dividend,
        email: settings.email,
        grid: settings.grid,
        grid_yield: settings.grid_yield,
        resonance: settings.resonance,
      }, premium));
      setSettings(premium ? updated : { ...updated, grid: settings.grid, grid_yield: settings.grid_yield, resonance: settings.resonance });
      if (premium) {
        setDraft(false);
        window.history.replaceState(null, "", "/notifications#settings");
      }
      setMessage(premium ? "提醒设置已保存" : "普通提醒已保存；高级提醒草稿尚未生效，升级后需再次确认保存。");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setAdvancedDenied(true);
        void fetchMe().then(setMe).catch(() => undefined);
      }
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="py-20 text-center text-sm text-muted">加载中…</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl text-ink">提醒</h1>
          <p className="mt-1 text-sm text-muted">
            自选涨跌、除息与网格提醒，共 {unread} 条未读
          </p>
        </div>
        {unread > 0 ? (
          <button
            type="button"
            onClick={onReadAll}
            className="rounded-sm border border-line bg-surface px-3 py-1.5 text-xs text-jade-deep hover:border-jade"
          >
            全部标记已读
          </button>
        ) : null}
      </div>

      {!settings && error ? <div role="alert" className="text-sm text-loss">{error} <button onClick={() => setAttempt((value) => value + 1)} className="underline">重新加载</button></div> : null}
      {settings ? (
        <section id="settings" className="card scroll-mt-24 p-5">
          <h2 className="text-base font-medium text-ink">提醒设置</h2>
          {draft ? <p role="status" className="mt-2 text-xs text-jade-deep">已保留提醒草稿，请确认后点击保存；页面返回不会自动启用提醒。</p> : null}
          {!premium ? <UpgradePrompt scene="alerts" profile={me} returnPath={alertDraftPath({ ...settings, price_pct: Number(threshold) >= 1 && Number(threshold) <= 20 ? Number(threshold) : settings.price_pct })} /> : null}
          <div className="mt-4 flex flex-wrap items-end gap-5 text-sm">
            <label className="flex flex-col gap-1 text-xs text-muted">
              涨跌阈值
              <span className="flex items-center gap-2">
                <input
                  type="number"
                  min="1"
                  max="20"
                  step="0.5"
                  value={threshold}
                  onChange={(event) => { setDraft(true); setThreshold(event.target.value); setMessage(null); }}
                  className="w-24 rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink"
                />
                %
              </span>
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-ink-soft">
              <input
                type="checkbox"
                checked={settings.dividend}
                onChange={(event) =>
                  editSettings({ ...settings, dividend: event.target.checked })
                }
              />
              除息提醒
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-ink-soft">
              <input
                type="checkbox"
                checked={settings.grid}
                onChange={(event) =>
                  editSettings({ ...settings, grid: event.target.checked })
                }
              />
              网格提醒{!premium ? "（会员，暂存草稿）" : ""}
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted">
              网格目标
              <select
                value={settings.grid_yield}
                disabled={!settings.grid}
                onChange={(event) =>
                  editSettings({ ...settings, grid_yield: Number(event.target.value) })
                }
                className="rounded-sm border border-line bg-surface px-2.5 py-2 text-sm text-ink disabled:opacity-50"
              >
                {[4, 4.5, 5, 5.5, 6].map((value) => (
                  <option key={value} value={value}>
                    {value}%
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-ink-soft">
              <input
                type="checkbox"
                checked={settings.resonance}
                onChange={(event) =>
                  editSettings({ ...settings, resonance: event.target.checked })
                }
              />
              低估值 + 低位共振{!premium ? "（会员，暂存草稿）" : ""}
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-ink-soft">
              <input
                type="checkbox"
                checked={settings.email}
                onChange={(event) =>
                  editSettings({ ...settings, email: event.target.checked })
                }
              />
              邮件提醒
            </label>
            <button
              type="button"
              onClick={onSaveSettings}
              disabled={saving}
              className="rounded-sm bg-ink px-4 py-2 text-sm font-medium text-paper disabled:opacity-50"
            >
              {saving ? "保存中…" : premium ? "保存" : "保存普通提醒"}
            </button>
          </div>
          {message ? <p className="mt-3 text-xs text-jade-deep">{message}</p> : null}
          {error ? <p className="mt-3 text-xs text-loss">{error}</p> : null}
          <p className="mt-4 text-xs text-muted">
            邮件提醒需要已验证邮箱；未验证时只生成站内提醒。
          </p>
        </section>
      ) : null}

      <section className="card overflow-hidden">
        <div className="divide-y divide-line">
          {items.map((item) => (
            <div
              key={item.id}
              className={`flex gap-3 p-4 ${item.read ? "" : "bg-jade-soft/25"}`}
            >
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                  item.read ? "bg-line" : "bg-jade"
                }`}
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-medium text-ink">{item.title}</p>
                  <span className="tnum text-[11px] text-muted">
                    {item.created_at.slice(0, 16).replace("T", " ")}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-ink-soft">{item.body}</p>
                <div className="mt-2 flex items-center gap-3 text-xs">
                  {item.link ? (
                    <Link href={item.link} className="text-jade-deep hover:underline">
                      查看详情
                    </Link>
                  ) : null}
                  {!item.read ? (
                    <button
                      type="button"
                      onClick={() => onRead(item.id)}
                      className="text-muted hover:text-ink"
                    >
                      标记已读
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </div>
        {items.length === 0 ? (
          <div className="px-4 py-16 text-center text-sm text-muted">
            暂无提醒。去自选页添加股票或 ETF，触发涨跌/除息后会在这里显示。
          </div>
        ) : null}
      </section>
    </div>
  );
}
