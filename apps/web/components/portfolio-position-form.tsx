"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { getToken } from "@/lib/auth";
import { portfolioRequest, PortfolioRequestError } from "@/lib/portfolio";
import {
  amount,
  basisLabels,
  defaultPreferences,
  inputTotal,
  kindLabels,
  shanghaiToday,
  type Basis,
  type Entry,
  type Holdings,
  type Kind,
  type Position,
  type PositionInput,
  type Preferences,
  type Preview,
  type StockChoice,
} from "@/lib/portfolio-positions";
import { PortfolioStockPicker } from "@/components/portfolio-stock-picker";

const input =
  "w-full min-w-0 rounded-lg border border-line bg-surface px-3 py-3 text-sm focus:outline-jade";
const button =
  "rounded-lg border border-line px-4 py-2 text-sm disabled:opacity-50 hover:border-jade";
const card = "space-y-4 rounded-xl border border-line bg-surface p-5 sm:p-6";
export function PortfolioPositionForm({
  accountId,
  version,
  positions,
  initialPosition,
  initialKind = "snapshot",
  correction,
  tradeTabs = false,
  onSaved,
  onCancel,
  onError,
}: {
  accountId: string;
  version: number;
  positions: Position[];
  initialPosition?: Position;
  initialKind?: Kind;
  correction?: Entry;
  tradeTabs?: boolean;
  onSaved: (result: Holdings) => void;
  onCancel: () => void;
  onError: (err: unknown) => void;
}) {
  const [kind, setKind] = useState<Kind>(initialKind);
  const [stock, setStock] = useState<StockChoice | null>(
    initialPosition
      ? {
          code: initialPosition.code,
          name: initialPosition.name,
          exchange: "",
          currency: "CNY",
          is_active: true,
          listed_on: null,
        }
      : correction
        ? {
            code: correction.code,
            name: correction.code,
            exchange: "",
            currency: "CNY",
            is_active: true,
            listed_on: null,
          }
        : null,
  );
  const [quantity, setQuantity] = useState(correction?.quantity ?? "");
  const [date, setDate] = useState(correction?.event_date ?? shanghaiToday());
  const [basis, setBasis] = useState<Basis | "">(
    correction?.details?.basis ?? (correction ? "weighted" : ""),
  );
  const [mode, setMode] = useState<"per_share" | "total">(
    correction?.details?.input_mode ??
      (correction && ["opening", "adjustment"].includes(correction.kind)
        ? "total"
        : "per_share"),
  );
  const [cost, setCost] = useState(
    correction?.details?.input_value ??
      (correction
        ? ["opening", "adjustment"].includes(correction.kind)
          ? correction.total_cost
          : correction.price
        : ""),
  );
  const [fees, setFees] = useState(
    correction
      ? correction.details?.fees_known === false
        ? ""
        : correction.fees
      : "",
  );
  const [prefs, setPrefs] = useState<Preferences>(
    initialPosition?.preferences ?? defaultPreferences(),
  );
  const [note, setNote] = useState("");
  const [evidence, setEvidence] = useState(correction?.evidence ?? "");
  const [order, setOrder] = useState(
    correction ? String(correction.day_order) : "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [payload, setPayload] = useState<PositionInput | null>(null);
  const previewDialog = useRef<HTMLDialogElement>(null);
  const helpDialog = useRef<HTMLDialogElement>(null);
  const alive = useRef(true);
  const token = useRef(getToken());
  const working = useRef(false);
  const lastRequest = useRef<{ content: string; id: string } | null>(null);
  const errorBox = useRef<HTMLParagraphElement>(null);
  const current = () => alive.current && token.current === getToken();
  const dirty = Boolean(stock || quantity || cost || note);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    const before = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", before);
    return () => window.removeEventListener("beforeunload", before);
  }, [dirty]);
  useEffect(() => {
    if (error) errorBox.current?.focus();
  }, [error]);
  const balance = ["snapshot", "opening", "adjustment", "rebase"].includes(
    kind,
  );
  const settingsOnly = kind === "preference";
  const reversal = kind === "reversal";
  const shareOnly = kind === "bonus" || kind === "reinvest";
  const existing = positions.find((p) => p.code === stock?.code);
  const duplicate = kind === "snapshot" && !!existing && !correction;
  const total = shareOnly
    ? "0"
    : balance && mode === "total"
      ? cost
      : inputTotal(
          quantity,
          cost,
          balance ? "0" : kind === "sell" && fees ? `-${fees}` : fees,
        );

  function report(err: unknown) {
    if (!current()) return;
    onError(err);
    setError(err instanceof Error ? err.message : "暂时无法保存，请重试。");
  }
  function changeStock(value: StockChoice | null) {
    if (stock && !value) {
      setQuantity("");
      setCost("");
      setFees("");
      setBasis("");
      setPrefs(defaultPreferences());
    }
    if (value) {
      const position = positions.find((p) => p.code === value.code);
      if (position) setPrefs(position.preferences);
    }
    setStock(value);
    setPreview(null);
  }
  function changeKind(value: Kind) {
    setKind(value);
    setCost(value === "bonus" || value === "reinvest" ? "0" : "");
    setFees("");
    setError("");
    setMode("per_share");
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (working.current || !current()) return;
    if (!stock) {
      setError("请搜索并选中股票，不能只输入名称。");
      return;
    }
    if (duplicate) {
      setError("这只股票已有记录，请记录买入，或在流水详情中更正原持仓。");
      return;
    }
    if (balance && !basis) {
      setError("请选择成本口径；不确定可以先保存参考值。");
      return;
    }
    const body = {
      expected_version: version,
      code: stock.code,
      kind,
      event_date: date,
        quantity: settingsOnly || reversal ? "0" : quantity,
        cost: settingsOnly || reversal ? "0" : shareOnly ? "0" : cost,
        input_mode: balance ? mode : ("per_share" as const),
        basis: basis || prefs.basis || ("weighted" as Basis),
        fees: balance || reversal || settingsOnly || shareOnly ? null : fees.trim() || null,
      preferences: {
        ...prefs,
        basis: balance ? (basis as Basis) : prefs.basis,
      },
      day_order: order ? Number(order) : null,
      note,
      evidence,
      reverses_id: correction?.id ?? null,
    };
    const content = JSON.stringify(body);
    if (lastRequest.current?.content !== content)
      lastRequest.current = { content, id: crypto.randomUUID() };
    const entry: PositionInput = {
      ...body,
      request_id: lastRequest.current.id,
    };
    working.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await portfolioRequest<Preview>(
        `/accounts/${accountId}/position-preview`,
        { method: "POST", body: JSON.stringify(entry) },
      );
      if (current()) {
        setPayload(entry);
        setPreview(result);
        previewDialog.current?.showModal();
      }
    } catch (err) {
      report(err);
    } finally {
      working.current = false;
      if (current()) setBusy(false);
    }
  }
  async function confirm() {
    if (!payload || !preview || working.current || !current()) return;
    working.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await portfolioRequest<Holdings>(
        `/accounts/${accountId}/position-confirm`,
        {
          method: "POST",
          body: JSON.stringify({
            entry: payload,
            preview_token: preview.preview_token,
          }),
        },
      );
      if (current()) {
        previewDialog.current?.close();
        onSaved(result);
      }
    } catch (err) {
      report(err);
      if (
        err instanceof PortfolioRequestError &&
        ["preview_expired", "preview_changed", "account_changed"].includes(
          err.code,
        )
      ) {
        setPreview(null);
        previewDialog.current?.close();
      }
    } finally {
      working.current = false;
      if (current()) setBusy(false);
    }
  }
  return (
    <div className="space-y-5" id="position-form">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-serif text-2xl">
          {correction
            ? reversal
              ? "撤销原记录"
              : "更正原记录"
            : settingsOnly
              ? "分组与分红参考"
              : kind === "sell"
                ? "记录卖出"
                : kind === "rebase"
                  ? "修正当前持仓"
                  : kind === "bonus"
                    ? "记录送股"
                    : kind === "reinvest"
                      ? "记录分红复投"
                      : tradeTabs
                        ? "记录交易"
                        : "添加持仓"}
        </h2>
        <button
          type="button"
          className={button}
          disabled={busy}
          onClick={() => {
            if (
              !dirty ||
              window.confirm("离开会清空尚未保存的内容，是否继续？")
            )
              onCancel();
          }}
        >
          返回持仓
        </button>
      </div>
      {tradeTabs && !correction && !settingsOnly ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="tablist" aria-label="交易类型">
          {(["buy", "sell", "bonus", "reinvest"] as const).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={kind === value}
              disabled={busy}
              className={`${button} py-3 ${kind === value ? "bg-jade text-white" : "bg-surface"}`}
              onClick={() => changeKind(value)}
            >
              {kindLabels[value]}
            </button>
          ))}
        </div>
      ) : null}
      {!tradeTabs &&
      !correction &&
      !settingsOnly &&
      !(["sell", "rebase"] as Kind[]).includes(kind) ? (
        <div
          className="grid grid-cols-2 gap-3"
          role="group"
          aria-label="录入方式"
        >
          {(["snapshot", "buy"] as const).map((k) => (
            <button
              type="button"
              key={k}
              disabled={busy}
              aria-pressed={kind === k}
              className={`${button} py-3 ${kind === k ? "bg-jade text-white" : "bg-surface"}`}
              onClick={() => changeKind(k)}
            >
              {k === "snapshot" ? "录入已有持仓" : "记录一笔买入"}
            </button>
          ))}
        </div>
      ) : null}
      <form
        className="space-y-5"
        data-portfolio-draft={dirty ? "" : undefined}
        onSubmit={submit}
      >
        <fieldset disabled={busy} className={card}>
          <h3 className="font-medium">
            1 · 选择股票{" "}
            <span className="ml-2 text-xs text-muted">A股 · 人民币</span>
          </h3>
          <PortfolioStockPicker
            accountId={accountId}
            selected={stock}
            onSelect={changeStock}
            disabled={busy || !!correction || !!initialPosition}
            onError={report}
          />
          {duplicate ? (
            <p role="status" className="text-sm text-loss">
              已有 {amount(existing?.quantity)} 股记录。
              <button
                type="button"
                className="ml-2 underline"
                onClick={() => {
                  changeKind("buy");
                  if (existing) setPrefs(existing.preferences);
                }}
              >
                记录一笔买入
              </button>
              ，或返回列表更正原持仓。
            </p>
          ) : null}
        </fieldset>
        {!settingsOnly && !reversal ? (
          <fieldset disabled={busy} className={card}>
            <h3 className="font-medium">
              2 · {balance ? "当前持仓信息" : "本笔成交信息"}
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="space-y-2 text-sm">
                <span>
                  {balance
                    ? "持仓数量（股）"
                    : shareOnly
                      ? kind === "bonus"
                        ? "送股数量（股）"
                        : "复投数量（股）"
                      : "成交数量（股）"}
                </span>
                <input
                  className={input}
                  aria-label="数量"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  inputMode="decimal"
                  maxLength={19}
                  autoComplete="off"
                  required
                  placeholder="例如：1000"
                />
              </label>
              <label className="space-y-2 text-sm">
                <span>
                  {["snapshot", "rebase"].includes(kind)
                    ? "持仓截至日期（日终）"
                    : balance
                      ? "原记录生效日期"
                      : shareOnly
                        ? kind === "bonus"
                          ? "送股日期"
                          : "复投日期"
                        : "成交日期"}
                </span>
                <input
                  className={input}
                  aria-label="日期"
                  type="date"
                  value={date}
                  min={stock?.listed_on ?? undefined}
                  max={shanghaiToday()}
                  onChange={(e) => setDate(e.target.value)}
                  required
                />
              </label>
            </div>
            <p className="text-xs leading-6 text-muted">
              {["snapshot", "rebase"].includes(kind)
                ? "填写该日全部交易完成后的持仓；当日交易已包含在快照中。不是首次买入日，不补算此前分红。"
                : balance
                  ? "保留旧版日期含义，更正不会改成日终快照。"
                  : "填写实际成交价，不使用今天行情替代历史价格。"}
            </p>
            {balance ? (
              <label className="block space-y-2 text-sm">
                <span>
                  成本口径{" "}
                  <button
                    type="button"
                    aria-label="查看区别"
                    className="ml-2 text-jade-deep underline"
                    onClick={() => helpDialog.current?.showModal()}
                  >
                    查看区别
                  </button>
                </span>
                <select
                  aria-label="成本口径"
                  className={input}
                  required
                  value={basis}
                  disabled={
                    !!correction &&
                    !(["snapshot", "rebase"] as Kind[]).includes(
                      correction.kind,
                    )
                  }
                  onChange={(e) => {
                    setBasis(e.target.value as Basis);
                    setCost("");
                  }}
                >
                  <option value="">请选择，与实际录入的口径一致</option>
                  {Object.entries(basisLabels).map(([k, v]) => (
                    <option value={k} key={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {shareOnly ? (
              <p className="rounded-lg bg-paper p-4 text-sm leading-6 text-ink-soft">
                {kind === "bonus"
                  ? "送股适用于红股、配股、拆股等非现金交易获得的股份。数量增加，总成本不变，平均成本会被摊薄。"
                  : "分红复投是用分红资金重新买入同一只股票。数量增加，不追加投入，总成本不变，平均成本会被摊薄。"}
              </p>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2 text-sm">
                  <span>
                    {balance
                      ? mode === "total"
                        ? "对应总额（元）"
                        : "当前每股成本（元/股）"
                      : "成交价（元/股）"}
                  </span>
                  <input
                    className={input}
                    aria-label="成本或成交价"
                    value={cost}
                    inputMode="decimal"
                    maxLength={20}
                    onChange={(e) => setCost(e.target.value)}
                    autoComplete="off"
                    required
                    placeholder={
                      balance && ["dividend", "net", "unknown"].includes(basis)
                        ? "允许正数、零或负数"
                        : "例如：20.00"
                    }
                  />
                </label>
                {!balance ? (
                  <label className="space-y-2 text-sm">
                    <span>本笔全部费用（元，可选）</span>
                    <input
                      className={input}
                      aria-label="费用"
                      inputMode="decimal"
                      maxLength={19}
                      value={fees}
                      onChange={(e) => setFees(e.target.value)}
                      placeholder="未填暂按0估算"
                      autoComplete="off"
                    />
                  </label>
                ) : null}
              </div>
            )}
            {balance ? (
              <button
                type="button"
                className="text-xs text-jade-deep underline"
                onClick={() => {
                  setMode(mode === "total" ? "per_share" : "total");
                  setCost("");
                }}
              >
                改为按{mode === "total" ? "每股成本" : "总额"}
                录入（清空原输入，避免混淆单位）
              </button>
            ) : null}
            {kind === "rebase" ? (
              <p className="text-sm text-loss">
                本次填写该日结束后的总持仓，替换当时的数量和所选成本余额，不作为新增买卖。此前记录保留；更早股息未补算。
              </p>
            ) : null}
            <div className="rounded-lg bg-paper p-4 text-sm">
              <p>
                {shareOnly
                  ? "本次不增加持仓成本"
                  : balance
                    ? basis === "weighted"
                      ? "加权持仓总成本"
                      : "所选口径对应总额"
                    : kind === "sell"
                      ? "卖出净收入"
                      : "买入总支出"}
              </p>
              <strong
                data-testid="input-total"
                className="mt-2 block break-all text-xl text-jade-deep"
              >
                {shareOnly ? "总成本不变" : `¥ ${amount(total)}`}
              </strong>
              <p className="mt-2 text-xs leading-6 text-muted">
                {shareOnly
                  ? "只增加股数，平均成本随数量增加而摊薄；不会产生买入支出或手续费。"
                  : balance
                    ? "历史费用已体现在填写的成本中，不再重复添加。只知道一种口径时，不推导其他口径。"
                    : fees.trim()
                      ? "已包含本笔填写的费用；最终金额以服务端预览为准。"
                      : "费用未知，当前暂按0估算；可在记录中更正补充。"}
              </p>
            </div>
          </fieldset>
        ) : null}
        {!reversal ? (
          <fieldset disabled={busy} className={card}>
            <h3 className="font-medium">
              {settingsOnly ? "2" : "3"} · 分红参考与分组{" "}
              <span className="text-xs text-muted">可选</span>
            </h3>
            {settingsOnly ? (
              <label className="block space-y-2 text-sm">
                <span>主展示成本口径（不更改账务）</span>
                <select
                  className={input}
                  value={prefs.basis}
                  onChange={(e) =>
                    setPrefs({ ...prefs, basis: e.target.value as Basis })
                  }
                >
                  {Object.entries(basisLabels).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <details open={settingsOnly || prefs.forecast !== "skip"}>
              <summary className="cursor-pointer text-sm">设置分红参考</summary>
              <div className="mt-4 space-y-3">
                <label className="block space-y-2 text-sm">
                  <span>参考口径</span>
                  <select
                    className={input}
                    aria-label="分红参考"
                    value={prefs.forecast}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        forecast: e.target.value as Preferences["forecast"],
                      })
                    }
                  >
                    <option value="skip">暂不设置</option>
                    <option value="12">过去12个月</option>
                    <option value="36">过去36个月年均</option>
                    <option value="60">过去60个月年均</option>
                    <option value="custom">自定义年度每股分红</option>
                  </select>
                </label>
                {prefs.forecast === "custom" ? (
                  <label className="block space-y-2 text-sm">
                    <span>税前年每股估计（元）</span>
                    <input
                      className={input}
                      aria-label="自定义分红"
                      inputMode="decimal"
                      value={prefs.custom ?? ""}
                      maxLength={19}
                      required
                      placeholder="允许为0"
                      onChange={(e) =>
                        setPrefs({ ...prefs, custom: e.target.value })
                      }
                    />
                  </label>
                ) : null}
                <p className="text-xs leading-6 text-muted">
                  按除息日统计已收录的普通现金分红，分别除以1、3或5年；预案、特别分红及重复记录不计入。数据可能不完整，预览时显示计算结果和缺失原因。历史与自定义参考均不生成应收或到账。
                </p>
              </div>
            </details>
            <label className="block space-y-2 text-sm">
              <span>所属分组</span>
              <input
                className={input}
                aria-label="分组"
                list="position-groups"
                maxLength={40}
                value={prefs.group}
                placeholder="未分组"
                onChange={(e) => setPrefs({ ...prefs, group: e.target.value })}
                autoComplete="off"
              />
              <datalist id="position-groups">
                {Array.from(
                  new Set(
                    positions.map((p) => p.preferences.group).filter(Boolean),
                  ),
                ).map((g) => (
                  <option key={g} value={g} />
                ))}
              </datalist>
            </label>
          </fieldset>
        ) : null}
        <fieldset disabled={busy} className={card}>
          <details open={!!correction || kind === "rebase"}>
            <summary className="cursor-pointer text-sm">
              {correction || kind === "rebase"
                ? "更正依据与原因"
                : "备注与高级选项"}
            </summary>
            <div className="mt-4 space-y-4">
              {correction ? (
                <p className="text-xs text-muted">
                  原记录会保留。保存后重算后续持仓，历史超卖会阻止提交。
                </p>
              ) : null}
              <label className="block space-y-2 text-sm">
                <span>
                  备注
                  {correction || kind === "rebase"
                    ? " / 更正原因（必填）"
                    : "（可选）"}
                </span>
                <textarea
                  className={input}
                  aria-label="备注"
                  value={note}
                  maxLength={500}
                  required={!!correction || kind === "rebase"}
                  onChange={(e) => setNote(e.target.value)}
                />
              </label>
              {["adjustment", "rebase"].includes(kind) ? (
                <label className="block space-y-2 text-sm">
                  <span>核对依据</span>
                  <textarea
                    className={input}
                    value={evidence}
                    required
                    maxLength={500}
                    onChange={(e) => setEvidence(e.target.value)}
                  />
                </label>
              ) : null}
              {!balance && !reversal && !settingsOnly ? (
                <label className="block space-y-2 text-sm">
                  <span>调整同日顺序（通常留空自动安排）</span>
                  <input
                    className={input}
                    aria-label="同日顺序"
                    type="number"
                    min={1}
                    max={1000000}
                    step={1}
                    value={order}
                    onChange={(e) => setOrder(e.target.value)}
                  />
                  <p className="text-xs text-muted">
                    数字越小越早；如补录先买后卖，可在查看流水后调整。
                  </p>
                </label>
              ) : null}
            </div>
          </details>
        </fieldset>
        <p
          ref={errorBox}
          tabIndex={-1}
          role="alert"
          className="text-sm text-loss"
        >
          {error}
        </p>
        <div className="sticky bottom-0 z-10 flex justify-end gap-3 bg-paper py-3">
          <button
            type="submit"
            className={`${button} bg-jade px-8 py-3 text-white`}
            disabled={busy || duplicate}
          >
            {busy ? "正在核对…" : "核对并预览"}
          </button>
        </div>
      </form>
      <dialog
        ref={helpDialog}
        className="m-auto w-[calc(100%-2rem)] max-w-xl rounded-xl border border-line bg-surface p-6 text-ink backdrop:bg-black/40"
      >
        <h3 className="font-serif text-xl">三种成本，不能互相猜算</h3>
        <p className="my-4 text-sm leading-7">
          教学示例（忽略费用）：买入1000股×5元，卖出500股×8元，收到净分红500元，剩500股。
        </p>
        <ul className="space-y-3 rounded-lg bg-paper p-4 text-sm">
          <li>
            加权平均：2500 ÷ 500 = <strong>5元/股</strong>
          </li>
          <li>
            摊薄成本：(5000 − 4000) ÷ 500 = <strong>2元/股</strong>
          </li>
          <li>
            分红摊薄：(5000 − 4000 − 500) ÷ 500 = <strong>1元/股</strong>
          </li>
        </ul>
        <p className="my-4 text-sm leading-7">
          只知道其中一种，另外两种保持未知。负摊薄成本表示该口径下净投入已回收，不等于没有风险。不同券商口径可能不同。
        </p>
        <button
          type="button"
          className={button}
          onClick={() => helpDialog.current?.close()}
        >
          知道了
        </button>
      </dialog>
      <dialog
        ref={previewDialog}
        onCancel={(e) => {
          if (busy) e.preventDefault();
        }}
        className="m-auto max-h-[90vh] w-[calc(100%-2rem)] max-w-xl overflow-y-auto rounded-xl border border-line bg-surface p-6 text-ink backdrop:bg-black/40"
      >
        {preview && payload ? (
          <>
            <h3 className="font-serif text-xl">
              确认{kindLabels[payload.kind]}
            </h3>
            <div className="my-4 space-y-3 text-sm leading-7">
              <strong>
                {preview.summary.stock.name} · {payload.code}
              </strong>
              <p>
                {preview.summary.date_semantics === "end_of_day"
                  ? "日终截至"
                  : "生效 / 成交日期"}
                ：{preview.summary.event_date}
              </p>
              {!settingsOnly && !reversal ? (
                <>
                  <p>数量：{amount(preview.summary.quantity)} 股</p>
                  <p>
                    {balance ? basisLabels[payload.basis] : "成交价"}：
                    {amount(payload.cost)}{" "}
                    {balance && payload.input_mode === "total"
                      ? "元（总额）"
                      : "元/股"}
                  </p>
                  <p className="break-all text-lg font-medium text-jade-deep">
                    {balance
                      ? "对应总额"
                      : payload.kind === "sell"
                        ? "卖出净收入"
                        : "买入总支出"}
                    ：¥ {amount(preview.summary.amount)}
                  </p>
                  {!balance ? (
                    <p>
                      费用：{amount(preview.summary.fees)} 元
                      {!preview.summary.fees_known
                        ? "（暂按0估算，待补充）"
                        : "（已填写）"}
                    </p>
                  ) : null}
                </>
              ) : null}
              <p>分组：{payload.preferences.group || "未分组"}</p>
              <p>
                分红参考：
                {preview.summary.forecast
                  ? preview.summary.forecast.annual_per_share != null
                    ? `${amount(preview.summary.forecast.annual_per_share)} 元/股/年（税前），年度参考 ¥${amount(preview.summary.forecast.annual_amount)}`
                    : preview.summary.forecast.reason_label || "分红记录待核对"
                  : "分红参考待加载"}
              </p>
              {preview.summary.forecast ? (
                <p className="text-xs leading-6 text-muted">
                  {preview.summary.forecast.note}
                </p>
              ) : null}
              <p>
                保存后持仓：
                {amount(preview.summary.resulting_position?.quantity ?? "0")} 股
              </p>
              {preview.summary.resulting_position ? (
                <div className="grid gap-2 rounded-lg bg-paper p-3 sm:grid-cols-3">
                  {(["weighted", "net", "dividend"] as const).map((b) => (
                    <div key={b}>
                      <p className="text-xs text-muted">
                        保存后{basisLabels[b]}
                      </p>
                      <p>
                        {preview.summary.resulting_position?.costs[b]
                          .per_share === null
                          ? "资料不足 / 已清仓"
                          : `${amount(preview.summary.resulting_position?.costs[b].per_share)} 元/股`}
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
              <p className="text-xs text-muted">{preview.summary.warning}</p>
            </div>
            <p role="alert" className="mb-4 text-sm text-loss">
              {error}
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                className={button}
                disabled={busy}
                onClick={() => previewDialog.current?.close()}
              >
                返回修改
              </button>
              <button
                type="button"
                className={`${button} bg-jade text-white`}
                disabled={busy}
                onClick={() => void confirm()}
              >
                {busy ? "正在保存…" : "确认保存"}
              </button>
            </div>
          </>
        ) : null}
      </dialog>
    </div>
  );
}
