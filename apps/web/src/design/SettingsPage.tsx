import { useState } from "react";
import { designApi, useLoad, type RoleTest } from "./api";
import { Banner, Crumbs, Spinner } from "./ui";
import { bytes, when } from "./lib";

export default function SettingsPage() {
  const status = useLoad(designApi.status, "settings");
  const [testing, setTesting] = useState<string | null>(null);
  const [tests, setTests] = useState<Record<string, RoleTest>>({});

  const test = async (role: string) => {
    setTesting(role);
    try {
      const result = await designApi.testRole(role);
      setTests((current) => ({ ...current, [role]: result }));
    } catch (problem) {
      setTests((current) => ({ ...current, [role]: { ok: false, seconds: 0, detail: problem instanceof Error ? problem.message : String(problem), at: new Date().toISOString() } }));
    } finally {
      setTesting(null);
    }
  };

  const data = status.data;
  return (
    <div className="page ds">
      <Crumbs items={[{ label: "Design Studio", to: "/design-studio" }, { label: "Settings" }]} />
      <header className="ds-head">
        <div>
          <h1>Connections and limits</h1>
          <p className="ds-sub">
            Design Studio uses <b>your</b> Microsoft Foundry deployments. Pipelines ask for a <i>role</i> (text, image,
            video, voice), and this install maps each role to a deployment. Keys never reach the browser: configuration
            lives in the service's environment (<code>services/design-api/.env</code>), and this page shows status and tests.
          </p>
        </div>
      </header>
      {status.error && <Banner kind="error">{status.error}</Banner>}
      {data && (
        <div className="ds-grid2" style={{ gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)", alignItems: "start" }}>
          <section className="ds-card">
            <h3>Model roles</h3>
            <div className="ds-scroll-x">
              <table className="ds-table">
                <thead>
                  <tr><th>Role</th><th>Resource / deployment</th><th>Status</th><th aria-label="Test" /></tr>
                </thead>
                <tbody>
                  {data.roles.map((role) => {
                    const result = tests[role.role] ?? role.last_test;
                    return (
                      <tr key={role.role}>
                        <td><b>{role.label}</b>{role.note && <div className="ds-tiny ds-muted">{role.note}</div>}</td>
                        <td className="ds-mono ds-small">{role.configured ? `${role.resource} / ${role.deployment}` : "not configured"}</td>
                        <td>
                          {!role.configured ? <span className="ds-chip bad">not set</span>
                            : result ? <span className={`ds-chip ${result.ok ? "ok" : "bad"}`} title={result.detail}>{result.ok ? `ready · ${result.seconds.toFixed(1)} s` : "failed"}</span>
                              : <span className="ds-chip">configured</span>}
                          {result && <div className="ds-tiny ds-muted" style={{ marginTop: 4, maxWidth: 320 }}>{result.detail}</div>}
                        </td>
                        <td>
                          <button type="button" className="ds-btn sm" disabled={!role.configured || testing !== null} onClick={() => void test(role.role)}>
                            {testing === role.role ? <Spinner size={12} /> : null} Test
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {data.text_models.length > 0 && (
              <p className="ds-small" style={{ marginTop: 10 }}>
                <b>Text models a run can choose:</b>{" "}
                {data.text_models.map((name) => <span key={name} className="ds-chip model" style={{ marginRight: 4 }}>{name}</span>)}
                <span className="ds-tiny ds-muted"> · set with <code>DESIGN_TEXT_MODELS</code>; the defaults are the two text roles above.</span>
              </p>
            )}
            <p className="ds-tiny ds-muted" style={{ marginTop: 8 }}>
              Text tests make one tiny call (it counts toward the text cap). Image, video and voice tests only check
              that the endpoint answers and your sign-in works; they don't generate anything.
            </p>
          </section>
          <div className="ds-stack">
            <section className="ds-card">
              <h3>Where this runs</h3>
              <dl className="ds-kv">
                <dt>Install</dt><dd>{data.install}</dd>
                <dt>Auth</dt><dd>{data.auth}</dd>
                <dt>Data</dt><dd className="ds-mono ds-small">{data.data_dir}</dd>
                <dt>Storage</dt><dd>{bytes(data.storage_bytes)}</dd>
                <dt>Tools</dt>
                <dd className="ds-row">
                  {Object.entries(data.tools).map(([tool, ok]) => <span key={tool} className={`ds-chip ${ok ? "ok" : "warn"}`}>{tool}{ok ? "" : " missing"}</span>)}
                </dd>
                <dt>Backup</dt><dd>Export run bundles from History; import them on the other install.</dd>
              </dl>
            </section>
            <section className="ds-card">
              <h3>Daily caps</h3>
              <dl className="ds-kv">
                {Object.entries(data.caps).map(([key, cap]) => (
                  <div key={key} style={{ display: "contents" }}>
                    <dt>{cap.label}</dt>
                    <dd>{cap.used} of {cap.cap} today{cap.detail ? ` · ${cap.detail}` : ""}</dd>
                  </div>
                ))}
              </dl>
              <p className="ds-tiny ds-muted" style={{ marginTop: 8 }}>
                Caps protect the subscription when the app is reachable from the home server. Blocked or failed calls
                give their unit back. Change them with <code>DESIGN_CAP_*</code> variables.
              </p>
            </section>
            {data.video_retirement && (
              <section className="ds-card">
                <h3>Video model lifecycle</h3>
                <p className="ds-small ds-dim">
                  Sora 2 (2025-12-08) retires {data.video_retirement.on}
                  {data.video_retirement.days_left >= 0 ? ` (${data.video_retirement.days_left} days left)` : " (retired)"}.
                  Finished takes stay in history. When a new video model is deployed, point <code>DESIGN_VIDEO_DEPLOYMENT</code> at it.
                </p>
              </section>
            )}
            <section className="ds-card">
              <h3>Students</h3>
              <p className="ds-small ds-dim">
                To use Design Studio, students connect <b>their own</b> Foundry resource (the same way the AI Fit
                Analyzer needs their Copilot): copy <code>services/design-api/.env.example</code> to <code>.env</code>, fill in
                their endpoints, run <code>az login</code>, then <code>npm run dev</code>. Without Azure,{" "}
                <code>DESIGN_PROVIDER_MODE=fake</code> runs the whole flow with placeholder media.
              </p>
              <p className="ds-tiny ds-muted" style={{ marginTop: 6 }}>Status loaded {when(new Date().toISOString())}.</p>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
