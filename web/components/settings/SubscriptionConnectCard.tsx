// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.
"use client";

import { useState } from "react";
import { CheckCircle2, Loader2, PlugZap } from "lucide-react";
import { useTranslation } from "react-i18next";
import ProviderIcon from "@/components/common/ProviderIcon";
import { apiFetch, apiUrl } from "@/lib/api";
import { useSettings } from "@/features/settings/store/SettingsStore";
import { registryButton, registryPrimary } from "./RegistryControls";
import { subPanelClass } from "./shared";

type Target = {
  provider: "claude_code" | "antigravity_acp";
  label: string;
  plan: string;
  cli: string;
};

const TARGETS: Target[] = [
  { provider: "claude_code", label: "Claude Code", plan: "Claude Pro / Max", cli: "claude" },
  { provider: "antigravity_acp", label: "Antigravity", plan: "Google AI Pro", cli: "agy" },
];

type Status = { kind: "idle" | "busy" | "ok" | "error"; text?: string };

/** One-click sign-in providers: no URL or API key, the local CLI's login is used. */
export function SubscriptionConnectCard() {
  const { t } = useTranslation();
  const { catalog, reloadSettings } = useSettings();
  const [status, setStatus] = useState<Record<string, Status>>({});
  const activeProfile = catalog?.services?.llm?.profiles?.find(
    (p) => p.id === catalog?.services?.llm?.active_profile_id,
  );
  const activeBinding = activeProfile?.binding ?? "";

  const connect = async (target: Target) => {
    setStatus((s) => ({ ...s, [target.provider]: { kind: "busy" } }));
    try {
      const response = await apiFetch(apiUrl("/api/settings/quick-connect"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: target.provider }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          typeof payload?.detail === "string" ? payload.detail : t("Could not connect."),
        );
      }
      await reloadSettings();
      const model = payload?.connected?.model ?? "";
      const taskModel = payload?.connected?.task_model ?? "";
      setStatus((s) => ({
        ...s,
        [target.provider]: {
          kind: "ok",
          text: t("Connected. Chat uses {{model}}, background tasks use {{taskModel}}.", {
            model,
            taskModel,
          }),
        },
      }));
    } catch (error) {
      setStatus((s) => ({
        ...s,
        [target.provider]: {
          kind: "error",
          text: error instanceof Error ? error.message : String(error),
        },
      }));
    }
  };

  return (
    <section
      aria-label={t("Connect a subscription")}
      className={`min-w-0 space-y-3 p-4 ${subPanelClass}`}
    >
      <div>
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <PlugZap size={15} aria-hidden />
          {t("Connect a subscription")}
        </h3>
        <p className="mt-1 text-[13px] text-[var(--muted-foreground)]">
          {t(
            "Uses the account you signed into in the local CLI. No URL or API key. Connecting makes it the chat model.",
          )}
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {TARGETS.map((target) => {
          const state = status[target.provider] ?? { kind: "idle" };
          const active = activeBinding === target.provider;
          return (
            <div
              key={target.provider}
              className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--border)] p-3"
            >
              <div className="flex items-center gap-2">
                <ProviderIcon provider={target.provider} size={16} />
                <span className="text-[13px] font-medium">{target.label}</span>
                <span className="text-[12px] text-[var(--muted-foreground)]">
                  {target.plan} · <code>{target.cli}</code>
                </span>
              </div>
              <button
                type="button"
                disabled={state.kind === "busy"}
                onClick={() => connect(target)}
                className={active ? registryButton : registryPrimary}
              >
                {state.kind === "busy" ? (
                  <Loader2 size={14} className="animate-spin" aria-hidden />
                ) : active ? (
                  <CheckCircle2 size={14} aria-hidden />
                ) : null}
                {active
                  ? t("In use · reconnect {{name}}", { name: target.label })
                  : t("Connect {{name}}", { name: target.label })}
              </button>
              {state.text ? (
                <p
                  role="status"
                  className={`text-[12px] ${state.kind === "error" ? "text-red-600 dark:text-red-400" : "text-[var(--muted-foreground)]"}`}
                >
                  {state.text}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
